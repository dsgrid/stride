from datetime import datetime
from typing import Any, Literal, get_args
from zoneinfo import ZoneInfo

# Re-export types that will be used by utils
ConsumptionBreakdown = Literal["End Use", "Sector"]
TimeGroup = Literal["Seasonal", "Seasonal and Weekday/Weekend", "Weekday/Weekend"]
TimeGroupAgg = Literal["Average Day", "Peak Day", "Minimum Day", "Median Day"]
Unit = Literal["kW", "MW", "GW", "MWh", "GWh", "TWh"]
SecondaryMetric = Literal[
    "GDP",
    "GDP Per Capita",
    "Human Development Index",
    "Population",
]
WeatherVar = Literal[
    "BAIT",
    "HDD",
    "CDD",
    "Temperature",
    "Solar_Radiation",
    "Wind_Speed",
    "Dew_Point",
    "Humidity",
]
Sectors = Literal["Commercial", "Industrial", "Residential", "Transportation", "Other"]
ChartType = Literal["Area", "Line"]
ResampleOptions = Literal["Hourly", "Daily Mean", "Weekly Mean"]
Season = Literal["Spring", "Summer", "Fall", "Winter"]


# Season and time constants
SPRING_DAY_START = 31 + 28 + 20
SPRING_DAY_END = 31 + 28 + 31 + 30 + 31
FALL_DAY_START = 31 + 28 + 31 + 30 + 31 + 30 + 31 + 22
FALL_DAY_END = 31 + 28 + 31 + 30 + 31 + 30 + 31 + 30 + 31 + 30 + 21
DEFAULT_FIRST_SATURDAY_HOUR = 5 * 24
HOURS_PER_WEEK = 168


def literal_to_list(
    literal: Any, include_none_str: bool = False, prefix: str | None = None
) -> list[str]:
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

    # Convert None values to string representation
    result = [str(r) if r is not None else "None" for r in result]

    if prefix:
        result = [f"{prefix}{r}" for r in result]
    if include_none_str and "None" not in result:
        result.insert(0, "None")

    return result


def local_time_expr(time_zone: str, column: str = "timestamp") -> str:
    """Return a SQL expression that converts a TIMESTAMPTZ column to naive local time.

    stride stores hourly timestamps as absolute instants (TIMESTAMPTZ) and runs database
    sessions in UTC. Always derive local labels (date, day of year, weekday, hour of day)
    from this expression rather than extracting fields from the bare TIMESTAMPTZ column,
    which would silently use the session time zone.

    Parameters
    ----------
    time_zone : str
        IANA time zone name, normally the project's standard time zone (e.g., 'Etc/GMT-1')
    column : str, optional
        Name of the TIMESTAMPTZ column, by default "timestamp"

    Returns
    -------
    str
        SQL expression, e.g., "timezone('Etc/GMT-1', timestamp)"
    """
    ZoneInfo(time_zone)  # Raises if the time zone is invalid; also guards the SQL literal.
    return f"timezone('{time_zone}', {column})"


def format_utc_offset(time_zone: str) -> str:
    """Return the UTC offset of a fixed-offset (standard) time zone, e.g., 'UTC+01:00'.

    The offset is evaluated on January 1 of a non-leap year, which is standard time in both
    hemispheres for zones that observe daylight saving time.
    """
    offset = datetime(2001, 1, 1, tzinfo=ZoneInfo(time_zone)).utcoffset()
    assert offset is not None
    total_minutes = int(offset.total_seconds() // 60)
    sign = "+" if total_minutes >= 0 else "-"
    hours, minutes = divmod(abs(total_minutes), 60)
    return f"UTC{sign}{hours:02d}:{minutes:02d}"


def generate_season_case_statement(day_col: str = "day_of_year") -> str:
    """
    Generate a SQL CASE statement to determine season based on day of year.

    Parameters
    ----------
    day_col : str, optional
        Name of the day of year column or expression, by default "day_of_year"

    Returns
    -------
    str
        SQL CASE statement that returns season name
    """
    return f"""CASE
        WHEN ({day_col}) >= {SPRING_DAY_START} AND ({day_col}) < {SPRING_DAY_END} THEN 'Spring'
        WHEN ({day_col}) >= {SPRING_DAY_END} AND ({day_col}) < {FALL_DAY_START} THEN 'Summer'
        WHEN ({day_col}) >= {FALL_DAY_START} AND ({day_col}) < {FALL_DAY_END} THEN 'Fall'
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


def build_order_by_clause(
    group_by: TimeGroup, breakdown: ConsumptionBreakdown | None = None
) -> str:
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
    breakdown: ConsumptionBreakdown | None = None,
    *,
    time_zone: str,
) -> tuple[str, list[Any]]:
    """
    Build a parameterized SQL query for seasonal load analysis.

    Seasons, weekday/weekend, day of year, and hour of day are all evaluated in local time
    (``time_zone``), not in the database session's time zone.

    Parameters
    ----------
    table_name : str
        Name of the energy projection table
    country : str
        Country identifier
    scenario : str
        Scenario name
    years : list[int]
        List of model years
    group_by : TimeGroup
        Time grouping option
    agg : TimeGroupAgg
        Aggregation method
    breakdown : ConsumptionBreakdown, optional
        Optional breakdown by sector or end use
    time_zone : str
        Time zone in which to evaluate local labels (the project's standard time zone)

    Returns
    -------
    tuple[str, list[Any]]
        Tuple containing the SQL query string and list of parameters
    """
    # Base parameters
    params: list[Any] = [country, scenario, years]

    # Build WHERE clause using ANY for years
    where_clause = """
    WHERE geography = ?
    AND scenario = ?
    AND model_year = ANY(?)
    """

    local_ts = local_time_expr(time_zone)

    # Extract day of year from timestamp for season determination
    day_of_year_expr = f"EXTRACT(DOY FROM {local_ts})"

    # Seasonal mapping using day of year
    season_case = generate_season_case_statement(day_of_year_expr)

    # Day type mapping
    # ISO day of week: 1=Monday ... 6=Saturday, 7=Sunday
    day_type_case = f"""
    CASE
        WHEN ISODOW({local_ts}) IN (6, 7) THEN 'Weekend'
        ELSE 'Weekday'
    END"""

    # Hour extraction
    hour_extract = f"EXTRACT(HOUR FROM {local_ts}) as hour_of_day"

    # Day of year extraction for proper daily aggregation
    day_of_year_extract = f"EXTRACT(DOY FROM {local_ts}) as day_of_year"

    # Determine aggregation function using the existing helper
    agg_func = get_aggregation_function(agg)

    # Build CTE SELECT and GROUP BY clauses
    cte_select_cols = ["scenario", "model_year as year"]
    cte_group_cols = ["scenario", "model_year"]

    if "Seasonal" in group_by:
        cte_select_cols.append(f"({season_case}) as season")
        cte_group_cols.append(f"({season_case})")

    if "Weekday/Weekend" in group_by:
        cte_select_cols.append(f"({day_type_case}) as day_type")
        cte_group_cols.append(f"({day_type_case})")

    # Add day of year and hour to CTE for proper daily aggregation
    cte_select_cols.append(day_of_year_extract)
    cte_select_cols.append(hour_extract)
    cte_group_cols.append("day_of_year")
    cte_group_cols.append("hour_of_day")

    if breakdown:
        breakdown_col = "metric" if breakdown == "End Use" else "sector"
        cte_select_cols.append(breakdown_col)
        cte_group_cols.append(breakdown_col)

    # Sum values by day and hour in the CTE
    cte_select_cols.append("SUM(value) as total_value")

    # Build outer query SELECT and GROUP BY clauses (excluding day_of_year)
    outer_select_cols = ["scenario", "year"]
    outer_group_cols = ["scenario", "year"]

    if "Seasonal" in group_by:
        outer_select_cols.append("season")
        outer_group_cols.append("season")

    if "Weekday/Weekend" in group_by:
        outer_select_cols.append("day_type")
        outer_group_cols.append("day_type")

    outer_select_cols.append("hour_of_day")
    outer_group_cols.append("hour_of_day")

    if breakdown:
        breakdown_col = "metric" if breakdown == "End Use" else "sector"
        outer_select_cols.append(breakdown_col)
        outer_group_cols.append(breakdown_col)

    # Apply aggregation function to the daily values (aggregating across day_of_year)
    outer_select_cols.append(f"{agg_func}(total_value) as value")

    sql = f"""
    WITH hourly_totals AS (
        SELECT {", ".join(cte_select_cols)}
        FROM {table_name}
        {where_clause}
        GROUP BY {", ".join(cte_group_cols)}
    )
    SELECT {", ".join(outer_select_cols)}
    FROM hourly_totals
    GROUP BY {", ".join(outer_group_cols)}
    ORDER BY {", ".join(outer_group_cols)}
    """

    return sql, params
