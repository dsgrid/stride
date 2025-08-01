from pathlib import Path
from typing import Any

from duckdb import DuckDBPyConnection, DuckDBPyRelation


def create_table_from_file(
    con: DuckDBPyConnection, name: str, path: Path | str, dtypes: dict[str, Any] | None = None
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

    Returns
    -------
    DuckDBPyRelation
        Relation for the created table
    """
    path_ = Path(path)
    match path_.suffix:
        case ".csv":
            _create_table_from_csv(con, name, path_, dtypes)
        case ".parquet":
            _create_table_from_parquet(con, name, path_)
        case _:
            msg = f"File type {path_.suffix} is not supported"
            raise NotImplementedError(msg)

    return con.table(name)


def _create_table_from_csv(
    con: DuckDBPyConnection, name: str, path: Path | str, dtypes: dict[str, Any] | None = None
) -> None:
    rel = con.read_csv(str(path), dtype=dtypes)  # noqa F841
    con.sql(f"CREATE TABLE {name} AS SELECT * from rel")


def _create_table_from_parquet(con: DuckDBPyConnection, name: str, path: Path | str) -> None:
    path_ = str(path) if Path(path).is_file() else f"{path}/**/*.parquet"
    con.sql(f"CREATE TABLE {name} AS SELECT * from read_parquet('{path_}')")
