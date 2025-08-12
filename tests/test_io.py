from pathlib import Path

import duckdb
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from stride.io import create_table_from_file, export_table


@pytest.fixture
def df_with_strings() -> pd.DataFrame:
    return pd.DataFrame({"a": [str(i) for i in range(10)], "b": [float(i) for i in range(10)]})


@pytest.fixture
def df_with_numbers() -> pd.DataFrame:
    return pd.DataFrame({"a": range(10), "b": [float(i) for i in range(10)]})


def test_create_table_from_csv_file(tmp_path: Path, df_with_strings: pd.DataFrame) -> None:
    df1 = df_with_strings
    filename = tmp_path / "data.csv"
    df1.to_csv(filename, index=False)
    con = duckdb.connect()
    create_table_from_file(
        con,
        "my_table",
        filename,
        dtypes={"a": duckdb.typing.VARCHAR, "b": duckdb.typing.DOUBLE},  # type: ignore
    )
    df2 = con.table("my_table").to_df()
    assert_frame_equal(df2, df1)


def test_create_table_from_parquet_file(tmp_path: Path, df_with_strings: pd.DataFrame) -> None:
    df1 = df_with_strings
    filename = tmp_path / "data.parquet"
    df1.to_parquet(filename, index=False)
    con = duckdb.connect()
    create_table_from_file(con, "my_table", filename)
    df2 = con.table("my_table").to_df()
    assert_frame_equal(df2, df1)


def test_create_table_from_unsupported(tmp_path: Path, df_with_numbers: pd.DataFrame) -> None:
    df1 = df_with_numbers
    filename = tmp_path / "data.unsupported"
    df1.to_parquet(filename, index=False)
    con = duckdb.connect()
    with pytest.raises(NotImplementedError):
        create_table_from_file(con, "my_table", filename)


@pytest.mark.parametrize("file_ext", [".csv", ".parquet"])
def test_export_table_to_files(
    tmp_path: Path, df_with_numbers: pd.DataFrame, file_ext: str
) -> None:
    df1 = df_with_numbers
    con = duckdb.connect()
    name = "my_table"
    con.register(name, df1)
    filename = tmp_path / f"{name}{file_ext}"
    assert not filename.exists()
    export_table(con, name, filename)
    assert filename.exists()
    match file_ext:
        case ".csv":
            df2 = pd.read_csv(filename)
        case ".parquet":
            df2 = pd.read_parquet(filename)
        case _:
            assert False, file_ext
    assert_frame_equal(df2, df1)


def test_export_table_to_unsupported(tmp_path: Path, df_with_numbers: pd.DataFrame) -> None:
    df1 = df_with_numbers
    con = duckdb.connect()
    name = "my_table"
    con.register(name, df1)
    filename = tmp_path / "data.unsupported"
    assert not filename.exists()
    with pytest.raises(NotImplementedError):
        export_table(con, name, filename)
    assert not filename.exists()
