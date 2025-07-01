from pathlib import Path

from duckdb import DuckDBPyConnection


def create_table_from_file(con: DuckDBPyConnection, name: str, path: Path | str) -> None:
    """Create a table in the database from a file path. Supports CSV and Parquet."""
    path_ = Path(path)
    match path_.suffix:
        case ".csv":
            _create_table_from_csv(con, name, path_)
        case ".parquet":
            _create_table_from_parquet(con, name, path_)


def _create_table_from_csv(con: DuckDBPyConnection, name: str, path: Path | str) -> None:
    con.sql(f"CREATE TABLE {name} AS SELECT * from read_csv('{path}')")


def _create_table_from_parquet(con: DuckDBPyConnection, name: str, path: Path | str) -> None:
    con.sql(f"CREATE TABLE {name} AS SELECT * from read_parquet('{path}/**/*.parquet')")
