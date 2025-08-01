from pathlib import Path

import duckdb
import pandas as pd
from pandas.testing import assert_frame_equal

from stride.io import create_table_from_file


def test_create_table_from_csv_file(tmp_path: Path) -> None:
    df = pd.DataFrame({"a": [str(i) for i in range(10)], "b": [float(i) for i in range(10)]})
    filename = tmp_path / "data.csv"
    df.to_csv(filename, index=False)
    con = duckdb.connect()
    create_table_from_file(
        con, "my_table", filename, dtypes={"a": duckdb.typing.VARCHAR, "b": duckdb.typing.DOUBLE}
    )
    df2 = con.table("my_table").to_df()
    assert_frame_equal(df, df2)


def test_create_table_from_parquet_file(tmp_path: Path) -> None:
    df = pd.DataFrame({"a": [str(i) for i in range(10)], "b": [float(i) for i in range(10)]})
    filename = tmp_path / "data.parquet"
    df.to_parquet(filename, index=False)
    con = duckdb.connect()
    create_table_from_file(con, "my_table", filename)
    df2 = con.table("my_table").to_df()
    assert_frame_equal(df, df2)
