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


def export_table(con: DuckDBPyConnection, name: str, path: Path | str) -> None:
    """Export a table in the database to a file. Supports CSV and Parquet, inferred from the
    file extension.
    """
    path_ = Path(path)
    match path_.suffix:
        case ".csv":
            _export_table_to_csv(con, name, path_)
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


def _export_table_to_csv(con: DuckDBPyConnection, name: str, path: Path | str) -> None:
    con.sql(f"COPY {name} TO '{path}' (FORMAT CSV)")


def _export_table_to_parquet(con: DuckDBPyConnection, name: str, path: Path | str) -> None:
    con.sql(f"COPY {name} TO '{path}' (FORMAT PARQUET)")


def _create_cmd(replace: bool) -> str:
    return "CREATE OR REPLACE" if replace else "CREATE"
