from datetime import datetime
from typing import Literal, Sequence

import pandas as pd
from duckdb import DuckDBPyConnection


def compute_total_electricity_consumption_time_series(
    con: DuckDBPyConnection,
    table_name: str,
    after_time: datetime | None = None,
    before_time: datetime | None = None,
    pivot_dimension: Literal["end_use", "sector"] | None = None,
    sort_by: Sequence[str] | None = None,
) -> pd.DataFrame:
    """Compute a time series array of total electricity consumption.

    Parameters
    ----------
    con
        Connection to DuckDB database
    table_name
        Name of table in database to query
    after_time
        If set, only show timestamps after this value.
    before_time
        If set, only show timestamps before this value.
    pivot_dimension
        If set, pivot on this dimension with a sum of values.
    sort_by
        If set, sort by these columns.
    """
    rel = con.table(table_name)
    # TODO
    if after_time is not None:
        pass
    if before_time is not None:
        pass
    if pivot_dimension is not None:
        rel = con.sql(
            f"""
            PIVOT {rel.alias}
            ON {pivot_dimension}
            USING SUM(value)
        """
        )
    if sort_by is not None:
        rel = rel.sort(*sort_by)
    return rel.to_df()
