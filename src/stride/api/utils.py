from typing import Literal, get_args

# Re-export types that will be used by utils
ConsumptionBreakdown = Literal["End Use", "Sector"]
TimeGroup = Literal["Seasonal", "Seasonal and Weekday/Weekend", "Weekday/Weekend"]
TimeGroupAgg = Literal["Average Day", "Peak Day", "Minimum Day", "Median Day"]

# Season and time constants
SPRING_DAY_START = 31 + 28 + 20
SPRING_DAY_END = 31 + 28 + 31 + 30 + 31
FALL_DAY_START = 31 + 28 + 31 + 30 + 31 + 30 + 31 + 22
FALL_DAY_END = 31 + 28 + 31 + 30 + 31 + 30 + 31 + 30 + 31 + 30 + 21
DEFAULT_FIRST_SATURDAY_HOUR = 5 * 24
HOURS_PER_WEEK = 168


def literal_to_list(literal, include_none_str=False, prefix=None) -> list[str]:
    """
    Convert a Literal type to a list of strings.

    Parameters
    ----------
    literal : Literal
        A typing.Literal type to convert to list
    include_none_str : bool, optional
        Whether to prepend "None" to the result list, by default False
    prefix : str, optional
        Optional prefix to prepend to each item, by default None

    Returns
    -------
    list[str]
        List of string values from the Literal type
    """
    result = list(get_args(literal)) if hasattr(literal, "__args__") else list(get_args(literal))

    if prefix:
        result = [f"{prefix}{r}" for r in result]
    if include_none_str:
        result.insert(0, "None")

    return result


def generate_season_case_statement(hour_col: str = "hour") -> str:
    """
    Generate a SQL CASE statement to determine season based on hour of year.

    Parameters
    ----------
    hour_col : str, optional
        Name of the hour column or expression, by default "hour"

    Returns
    -------
    str
        SQL CASE statement that returns season name
    """
    spring_hour_start = SPRING_DAY_START * 24
    spring_hour_end = SPRING_DAY_END * 24
    fall_hour_start = FALL_DAY_START * 24
    fall_hour_end = FALL_DAY_END * 24

    return f"""CASE
        WHEN ({hour_col}) >= 0 AND ({hour_col}) < {spring_hour_start} THEN 'Winter'
        WHEN ({hour_col}) >= {spring_hour_start} AND ({hour_col}) < {spring_hour_end} THEN 'Spring'
        WHEN ({hour_col}) >= {spring_hour_end} AND ({hour_col}) < {fall_hour_start} THEN 'Summer'
        WHEN ({hour_col}) >= {fall_hour_start} AND ({hour_col}) < {fall_hour_end} THEN 'Fall'
        WHEN ({hour_col}) >= {fall_hour_end} AND ({hour_col}) < 8760 THEN 'Winter'
        ELSE 'Winter'
    END"""


def generate_weekday_weekend_case_statement(hour_col: str = "hour") -> str:
    """
    Generate a SQL CASE statement to determine if an hour falls on a weekday or weekend.

    Parameters
    ----------
    hour_col : str, optional
        Name of the hour column or expression, by default "hour"

    Returns
    -------
    str
        SQL CASE statement that returns 'Weekday' or 'Weekend'
    """
    weekend_start = DEFAULT_FIRST_SATURDAY_HOUR

    return f"""CASE
        WHEN (({hour_col}) % {HOURS_PER_WEEK}) >= {weekend_start} THEN 'Weekend'
        ELSE 'Weekday'
    END"""


def get_breakdown_column(breakdown: ConsumptionBreakdown) -> str:
    """Get the database column name for a given breakdown type."""
    return "metric" if breakdown == "End Use" else "sector"


def get_aggregation_function(agg: TimeGroupAgg) -> str:
    """Get the SQL aggregation function for a given aggregation type."""
    agg_mapping = {
        "Average Day": "AVG",
        "Peak Day": "MAX",
        "Minimum Day": "MIN",
        "Median Day": "MEDIAN",
    }
    return agg_mapping[agg]


def build_time_grouping_columns(
    group_by: TimeGroup, hour_of_year_expr: str
) -> tuple[list[str], list[str]]:
    """
    Build select and group by column lists for time grouping.

    Parameters
    ----------
    group_by : TimeGroup
        The time grouping option
    hour_of_year_expr : str
        SQL expression for hour of year calculation

    Returns
    -------
    tuple[list[str], list[str]]
        (select_columns, group_by_columns) for the time grouping
    """
    select_cols = []
    group_by_cols = []

    if "Seasonal" in group_by:
        season_case = generate_season_case_statement(hour_of_year_expr)
        select_cols.append(f"({season_case}) as season")
        group_by_cols.append(f"({season_case})")

    if "Weekday/Weekend" in group_by:
        weekday_case = generate_weekday_weekend_case_statement(hour_of_year_expr)
        select_cols.append(f"({weekday_case}) as day_type")
        group_by_cols.append(f"({weekday_case})")

    return select_cols, group_by_cols


def build_order_by_clause(group_by: TimeGroup, breakdown: ConsumptionBreakdown = None) -> str:
    """Build ORDER BY clause for seasonal queries."""
    order_cols = ["scenario", "year"]

    if "Seasonal" in group_by:
        order_cols.append("season")
    if "Weekday/Weekend" in group_by:
        order_cols.append("day_type")

    order_cols.append("hour_of_day")

    if breakdown:
        order_cols.append(get_breakdown_column(breakdown))

    return ", ".join(order_cols)


def build_seasonal_query(
    table_name: str,
    country: str,
    scenario: str,
    years: list[int],
    group_by: TimeGroup,
    agg: TimeGroupAgg,
    breakdown: ConsumptionBreakdown = None,
) -> str:
    """
    Build a complete SQL query for seasonal load analysis.

    Parameters
    ----------
    table_name : str
        Name of the energy projection table
    country : str
        Project country identifier
    scenario : str
        Scenario name
    years : list[int]
        List of years to include
    group_by : TimeGroup
        Time grouping option
    agg : TimeGroupAgg
        Aggregation function
    breakdown : ConsumptionBreakdown, optional
        Optional breakdown by sector/end use

    Returns
    -------
    str
        Complete SQL query string
    """
    # Base expressions
    hour_of_year_expr = "EXTRACT(DOY FROM timestamp) * 24 + EXTRACT(HOUR FROM timestamp) - 24"
    hour_of_day_expr = "EXTRACT(HOUR FROM timestamp)"

    # Base columns
    select_cols = ["scenario", "model_year as year", f"{hour_of_day_expr} as hour_of_day"]
    group_by_cols = ["scenario", "model_year", f"{hour_of_day_expr}"]

    # Add breakdown if specified
    if breakdown:
        breakdown_col = get_breakdown_column(breakdown)
        select_cols.append(breakdown_col)
        group_by_cols.append(breakdown_col)

    # Add time grouping columns
    time_select_cols, time_group_cols = build_time_grouping_columns(group_by, hour_of_year_expr)
    select_cols.extend(time_select_cols)
    group_by_cols.extend(time_group_cols)

    # Get aggregation function
    agg_func = get_aggregation_function(agg)

    # Build clauses
    select_clause = ", ".join(select_cols)
    group_by_clause = ", ".join(group_by_cols)
    order_by_clause = build_order_by_clause(group_by, breakdown)
    years_clause = ",".join(map(str, years))

    return f"""
    SELECT
        {select_clause},
        {agg_func}(value) as value
    FROM {table_name}
    WHERE geography = '{country}'
        AND scenario = '{scenario}'
        AND model_year IN ({years_clause})
    GROUP BY {group_by_clause}
    ORDER BY {order_by_clause}
    """
