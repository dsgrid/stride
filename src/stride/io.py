from pathlib import Path
from typing import Any

from duckdb import DuckDBPyConnection, DuckDBPyRelation


def create_table_from_file(
    con: DuckDBPyConnection,
    name: str,
    path: Path | str,
    dtypes: dict[str, Any] | None = None,
    replace: bool = False,
) -> DuckDBPyRelation:
    """Create a table in the database from a file path. Supports CSV and Parquet.

    Parameters
    ----------
    name
        Name of table to create
    path
        Path to data file
    dtypes
        Optional, data type of each column. Values should be DuckDB types.
        Recommended for CSV files. Not used with Parquet files.
    replace
        If True, invoke CREATE OR REPLACE TABLE instead of CREATE TABLE.

    Returns
    -------
    DuckDBPyRelation
        Relation for the created table
    """
    path_ = Path(path)
    match path_.suffix:
        case ".csv":
            _create_table_from_csv(con, name, path_, dtypes, replace=replace)
        case ".parquet":
            _create_table_from_parquet(con, name, path_, replace=replace)
        case _:
            msg = f"File type {path_.suffix} is not supported"
            raise NotImplementedError(msg)

    return con.table(name)


def export_table(
    con: DuckDBPyConnection, name: str, path: Path | str, time_zone: str | None = None
) -> None:
    """Export a table in the database to a file. Supports CSV and Parquet, inferred from the
    file extension.

    Parameters
    ----------
    time_zone
        Optional, time zone in which to write TIMESTAMPTZ columns to CSV files. The values
        include the UTC offset, so they remain unambiguous. Parquet files always store
        UTC-adjusted instants, so this has no effect on them.
    """
    path_ = Path(path)
    match path_.suffix:
        case ".csv":
            _export_table_to_csv(con, name, path_, time_zone=time_zone)
        case ".parquet":
            _export_table_to_parquet(con, name, path_)
        case _:
            msg = f"File type {path_.suffix} is not supported"
            raise NotImplementedError(msg)


def _create_table_from_csv(
    con: DuckDBPyConnection,
    name: str,
    path: Path | str,
    dtypes: dict[str, Any] | None = None,
    replace: bool = False,
) -> None:
    rel = con.read_csv(str(path), dtype=dtypes)  # noqa F841
    cmd = _create_cmd(replace)
    con.sql(f"{cmd} TABLE {name} AS SELECT * from rel")


def _create_table_from_parquet(
    con: DuckDBPyConnection, name: str, path: Path | str, replace: bool = False
) -> None:
    path_ = str(path) if Path(path).is_file() else f"{path}/**/*.parquet"
    cmd = _create_cmd(replace)
    con.sql(f"{cmd} TABLE {name} AS SELECT * from read_parquet('{path_}')")


def _export_table_to_csv(
    con: DuckDBPyConnection, name: str, path: Path | str, time_zone: str | None = None
) -> None:
    if time_zone is None:
        con.sql(f"COPY {name} TO '{path}' (FORMAT CSV)")
        return

    # DuckDB renders TIMESTAMPTZ values in the session time zone.
    row = con.execute("SELECT current_setting('TimeZone')").fetchone()
    assert row is not None
    orig_time_zone = row[0]
    con.execute(f"SET TimeZone = '{time_zone}'")
    try:
        con.sql(f"COPY {name} TO '{path}' (FORMAT CSV)")
    finally:
        con.execute(f"SET TimeZone = '{orig_time_zone}'")


def _export_table_to_parquet(con: DuckDBPyConnection, name: str, path: Path | str) -> None:
    con.sql(f"COPY {name} TO '{path}' (FORMAT PARQUET)")


def _create_cmd(replace: bool) -> str:
    return "CREATE OR REPLACE" if replace else "CREATE"
