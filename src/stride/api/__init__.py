from __future__ import annotations

"""
STRIDE UI Data API

This module provides a unified interface for querying electricity load and demand data
from a DuckDB database. The API offers methods
for retrieving annual consumption metrics, peak demand analysis, load duration curves,
timeseries comparisons, seasonal load patterns, and secondary metrics like economic
indicators and weather data.

Key Features:
- Support for scenario comparison and breakdown analysis
- Flexible time aggregation and grouping options
- Integration with secondary metrics (GDP, population, weather, etc.)


Lingering Questions/Comments:
1. We need some way of determining the valid model years. Preferably a fast lookup of the project config. (DONE)
2. For secondary metrics, how do we handle different versions of table overrides (e.g. Two versions of GDP)
3. What is "Absolute Value" in the Scenario Summary Stats? (Assuming total consumption (TWh))
4. In the timeseries charts, It seems like Daily or Weekly mean should be in separate dropdown category.
5. For Comparing two timeseries, we need to handle displaying the secondary axis weather variable for both model years
"""

import threading
from pathlib import Path
from typing import  Literal, TYPE_CHECKING, get_args
import pandas as pd

if TYPE_CHECKING:
    import duckdb
    from stride.models import ProjectConfig


ConsumptionBreakdown = Literal["End Use", "Sector"]
Unit = Literal["kW", "MW", "TW", "TWh"] # - ? Nice to have but not used
SecondaryMetric = Literal["GDP","GDP Per Capita","Human Development Index", "Percent EV Adoption", "Population", "Stock"]
WeatherVar = Literal["Humidity", "Temperature"]
Sectors = Literal["Commercial", "Industrial", "Residential", "Transportation", "Other"]
ChartType = Literal["Area", "Line"]
ResampleOptions = Literal["Daily Mean", "Weekly Mean"] # ? - Could be more concise by removing the word "mean"
TimeGroup = Literal["Seasonal", "Seasonal and Weekday/Weekend", "Weekday/Weekend"] # ? - Rename to something else? This corresponds to how we group days of the year.
TimeGroupAgg = Literal["Average Day", "Peak Day", "Minimum Day", "Median Day"]
Season = Literal["Spring", "Summer", "Fall", "Winter"]


def literal_to_list(literal, include_none_str=False, prefix=None) -> list[str]:
    """Converts a Literal to a list."""
    result = list(get_args(literal)) if hasattr(literal, '__args__') else list(get_args(literal))

    if prefix:
        result = [f"{prefix}{r}" for r in result]
    if include_none_str:
        result.insert(0, "None")

    return result


# Default Day of Year for equinoxes.
SPRING_DAY_START=31+28+20  # Always falls on march 20 or 21 (19 for a leap year)
SPRING_DAY_END=31+28+31+30+31 # Always falls on May 31st
FALL_DAY_START=31+28+31+30+31+30+31+22 # Always on September 22nd or 23rd.
FALL_DAY_END=31+28+31+30+31+30+31+30+31+30+21 # always on December 21st or 22nd


# NOTE HOUR 0 == Monday at 12/1 am?
DEFAULT_FIRST_SATURDAY_HOUR = 5*24
HOURS_PER_WEEK = 168
HOURS_PER_DAY = 24


# NOTE
# Go over naming scheme for override base tables (gdp, pop, etc.)
# Does each projection year start on a different day of the week? Or is it an day of year aligned extrapolation of a base year?
# It loks like timestamp is fixed (e.g. 2018-01-01), even for multiple model_years.

# TODO
# Convert to Tall table format.
# Load duration curves for single scenario, multiple years.
# Summary Statistics Query
# Secondary metric queries (GDP per capita is slightly different.)
# Weather (Temp and humidity). Waiting on what that schema looks like.
# Verify seasonal load lines are valid. (Seems to be the same for multiple years).
# Could verify with load duration curve for single scenario, multi years.

def _generate_season_case_statement(hour_col: str = "hour") -> str:
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

    Examples
    --------
    >>> case_stmt = _generate_season_case_statement()
    >>> print(case_stmt)
    CASE
        WHEN hour >= 0 AND hour < 1896 THEN 'Winter'
        WHEN hour >= 1896 AND hour < 3672 THEN 'Spring'
        WHEN hour >= 3672 AND hour < 6552 THEN 'Summer'
        WHEN hour >= 6552 AND hour < 8760 THEN 'Fall'
        ELSE 'Winter'
    END
    """
    # Convert day boundaries to hour boundaries
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

def _generate_weekday_weekend_case_statement(hour_col: str = "hour") -> str:
    """
    Generate a SQL CASE statement to determine if an hour falls on a weekday or weekend.

    Assumes hour 0 is Monday at midnight and uses the DEFAULT_FIRST_SATURDAY_HOUR
    constant to determine weekend periods.

    Parameters
    ----------
    hour_col : str, optional
        Name of the hour column or expression, by default "hour"

    Returns
    -------
    str
        SQL CASE statement that returns 'Weekday' or 'Weekend'

    Examples
    --------
    >>> case_stmt = _generate_weekday_weekend_case_statement()
    >>> print(case_stmt)
    CASE
        WHEN ({hour_col} % 168) >= 120 AND ({hour_col} % 168) < 168 THEN 'Weekend'
        ELSE 'Weekday'
    END
    """
    # Calculate weekend hours within a week (168 hours)
    # Saturday starts at hour 120 (5 * 24) and Sunday is hours 144-167 (6 * 24 to 7 * 24 - 1)
    weekend_start = DEFAULT_FIRST_SATURDAY_HOUR  # 120 (Saturday start)

    return f"""CASE
        WHEN (({hour_col}) % {HOURS_PER_WEEK}) >= {weekend_start} THEN 'Weekend'
        ELSE 'Weekday'
    END"""


class APIClient:
    """
    Singleton API client for querying STRIDE electricity load and demand data.

    This class provides a thread-safe singleton interface to a DuckDB database containing
    electricity consumption, demand, and related metrics data. It ensures only one database
    connection exists throughout the application lifecycle while providing convenient
    methods for common data queries used in dashboard visualizations.

    The client supports various data retrieval patterns including:
    - Annual consumption and peak demand metrics with optional breakdowns
    - Load duration curves for capacity planning analysis
    - Timeseries data with flexible resampling and grouping
    - Seasonal load pattern analysis
    - Secondary metrics integration (economic, demographic, weather data)

    Attributes
    ----------
    db : duckdb.DuckDBPyConnection
        The underlying DuckDB database connection
    project_config : ProjectConfig, optional
        The project configuration if provided
    energy_proj_table : str
        Name of the energy projection table
    project_country : str
        Country identifier for the project

    Examples
    --------
    >>> # Initialize with database path
    >>> client = APIClient("/path/to/database.db")
    >>>
    >>> # Initialize with ProjectConfig
    >>> client = APIClient(project_config=config, db_connection=conn)
    >>>
    >>> # Query annual consumption by sector
    >>> consumption = client.get_annual_electricity_consumption(
    ...     scenarios=["baseline", "high_growth"],
    ...     group_by="Sector"
    ... )
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, path_or_conn: str | Path | 'duckdb.DuckDBPyConnection' | None = None, project_config: 'ProjectConfig | None' = None):
        # Always create a new instance instead of singleton for development
        return super().__new__(cls)

    def __init__(
        self,
        path_or_conn: str | Path | 'duckdb.DuckDBPyConnection' | None = None,
        project_config: 'ProjectConfig | None' = None
    ):
        # Remove singleton behavior during development
        self.project_config = project_config

        # Set table name and country from config or defaults
        if project_config:
            self.energy_proj_table = "energy_projection"
            self.project_country = project_config.country
        else:
            # Fallback to original hardcoded values
            self.energy_proj_table = "energy_projection"
            self.project_country = "country_1"

        self._initialize_connection(path_or_conn)

    def _close_existing_connection(self):
        """Close the existing database connection if it exists."""
        if hasattr(self, "db") and self.db:
            try:
                self.db.close()
                print("Database connection closed")
            except Exception as e:
                print(f"Error closing connection: {e}")
                pass

    def _initialize_connection(self, path_or_conn):
        """Initialize the database connection"""
        if path_or_conn is None:
            raise ValueError("Database connection, path, or connection string must be provided.")

        # Close any existing connection first
        self._close_existing_connection()

        if isinstance(path_or_conn, str):
            db_path = Path(path_or_conn)
            if not db_path.exists():
                raise FileNotFoundError(f"Database file not found: {db_path}")
            if not db_path.is_file():
                raise ValueError(f"Path is not a file: {db_path}")

            try:
                import duckdb
                # Try read-only connection first to avoid locks
                print(f"Attempting read-only connection to: {db_path}")
                self.db = duckdb.connect(str(db_path), read_only=True)
                print(f"Successfully connected to database: {db_path}")
            except duckdb.IOException as e:
                if "lock" in str(e).lower():
                    print(f"Database is locked. Error: {e}")
                    print("Try killing the process mentioned in the error or use 'pkill -f python'")
                    raise ConnectionError(f"Database is locked by another process. {e}")
                else:
                    raise ConnectionError(f"Failed to connect to database at {db_path}: {e}")
            except ImportError:
                raise ImportError("duckdb package is required but not installed")
            except Exception as e:
                raise ConnectionError(f"Failed to connect to database at {db_path}: {e}")

        elif isinstance(path_or_conn, Path):
            # Validate Path object
            if not path_or_conn.exists():
                raise FileNotFoundError(f"Database file not found: {path_or_conn}")
            if not path_or_conn.is_file():
                raise ValueError(f"Path is not a file: {path_or_conn}")
            # Create DuckDB connection
            try:
                import duckdb
                self.db = duckdb.connect(str(path_or_conn), read_only=True)
            except ImportError:
                raise ImportError("duckdb package is required but not installed")
            except Exception as e:
                raise ConnectionError(f"Failed to connect to database at {path_or_conn}: {e}")
        else:
            # Assume it's a DuckDB connection object
            try:
                # Basic validation - check if it has execute method
                if not hasattr(path_or_conn, 'execute'):
                    raise ValueError("Invalid database connection object - missing execute method")
                self.db = path_or_conn
            except Exception as e:
                raise ValueError(f"Invalid database connection: {e}")

        self._years = None
        self._scenarios = None

    def __del__(self):
        """Cleanup on object destruction."""
        self._close_existing_connection()

    @property
    def years(self) -> list[int]:
        """
        Get cached list of valid model years.

        Returns
        -------
        list[int]
            A list of valid model years from the database.
        """
        if self._years is None:
            self._years = self._fetch_years()
        return self._years

    @property
    def end_uses(self):
        """TODO Need end use data"""
        return []


    @property
    def scenarios(self) -> list[str]:
        """
        Get cached list of valid scenarios.

        Returns
        -------
        list[str]
            A list of valid scenarios from the database.
        """
        if self._scenarios is None:
            self._scenarios = self._fetch_scenarios()
        return self._scenarios

    def refresh_metadata(self) -> None:
        """
        Refresh cached years and scenarios by re-reading from database.
        Call this if the database content has changed.
        """
        self._years = None
        self._scenarios = None

    def _fetch_years(self) -> list[int]:
        """Fetch years from database."""
        sql = f"""
        SELECT DISTINCT model_year as year
        FROM {self.energy_proj_table}
        WHERE geography = '{self.project_country}'
        ORDER BY model_year
        """
        result = self.db.execute(sql).fetchall()
        return [row[0] for row in result]

    def _fetch_scenarios(self) -> list[str]:
        """Fetch scenarios from database."""
        sql = f"""
        SELECT DISTINCT scenario
        FROM {self.energy_proj_table}
        WHERE geography = '{self.project_country}'
        ORDER BY scenario
        """
        result = self.db.execute(sql).fetchall()
        return [row[0] for row in result]

    def _validate_scenarios(self, scenarios: list[str]) -> None:
        """Validate that all provided scenarios exist in the database."""
        if not scenarios:
            return

        valid_scenarios = set(self.scenarios)
        invalid_scenarios = [s for s in scenarios if s not in valid_scenarios]

        if invalid_scenarios:
            raise ValueError(f"Invalid scenarios: {invalid_scenarios}. Valid scenarios are: {list(valid_scenarios)}")

    def _validate_years(self, years: list[int]) -> None:
        """Validate that all provided years exist in the database."""
        if not years:
            return

        valid_years = set(self.years)
        invalid_years = [y for y in years if y not in valid_years]

        if invalid_years:
            raise ValueError(f"Invalid years: {invalid_years}. Valid years are: {list(valid_years)}")

    def get_years(self) -> list[int]:
        """
        Returns
        -------
        list[int]
            A list of valid model years. Used for validating inputs into api query functions.

        Examples
        --------
        >>> client = APIClient(path_or_conn)
        >>> years = client.get_years()
        >>> print(years)
        [2025, 2030, 2035, 2040, 2045, 2050]
        """
        return self.years


    def get_annual_electricity_consumption(
            self,
            scenarios: list[str] | None = None,
            years: list[int] | None = None,
            group_by: ConsumptionBreakdown | None = None,
    ) -> pd.DataFrame:
        """Queries the Total Annual Consumption for each scenario.

        Parameters
        ----------
        years : list[int], optional
            Valid projection years for the opened project. If None, uses all projection years.
        group_by : ConsumptionBreakdown, optional
            Optionally breakdown by Sector and end Use. If None, uses total.
        scenarios : list[str], optional
            Optional list of scenarios to filter by. If None, uses all scenarios available.

        Returns
        -------
        pd.DataFrame
            DataFrame with consumption values in tall format.

            Columns:
            - scenario: str, scenario name
            - year: int, projection year
            - sector/end_use: str, breakdown category (if group_by specified)
            - value: float, consumption value in TWh

        Examples
        --------
        >>> client = APIClient(path_or_conn)
        >>> # Get total consumption for all scenarios and years
        >>> df = client.get_annual_electricity_consumption()

        | scenario    | year | value |
        |-------------|------|-------|
        | baseline    | 2025 | 5500  |
        | baseline    | 2030 | 5900  |
        | high_growth | 2025 | 6000  |
        | high_growth | 2030 | 6500  |

        >>> # Get consumption by sector for specific scenarios
        >>> df = client.get_annual_electricity_consumption(
        ...     scenarios=["baseline", "high_growth"],
        ...     group_by="Sector"
        ... )

        | scenario    | year | sector      | value |
        |-------------|------|-------------|-------|
        | baseline    | 2025 | Commercial  | 1500  |
        | baseline    | 2025 | Industrial  | 2200  |
        | baseline    | 2025 | Residential | 1800  |
        | baseline    | 2030 | Commercial  | 1650  |
        | high_growth | 2025 | Commercial  | 1600  |
        """

        if years is None:
            years = self.years
        if scenarios is None:
            scenarios = self.scenarios

        # Validate inputs
        self._validate_scenarios(scenarios)
        self._validate_years(years)

        # Build SQL query based on group_by parameter
        if group_by:
            if group_by == "End Use":
                group_col = "metric"
            else:  # group_by == "Sector"
                group_col = "sector"
            sql = f"""
            SELECT scenario, model_year as year, {group_col}, SUM(value) as value
            FROM {self.energy_proj_table}
            WHERE geography = '{self.project_country}'
            AND scenario IN ('{"','".join(scenarios)}')
            AND model_year IN ({','.join(map(str, years))})
            GROUP BY scenario, model_year, {group_col}
            ORDER BY scenario, model_year, {group_col}
            """
        else:
            sql = f"""
            SELECT scenario, model_year as year, SUM(value) as value
            FROM {self.energy_proj_table}
            WHERE geography = '{self.project_country}'
            AND scenario IN ('{"','".join(scenarios)}')
            AND model_year IN ({','.join(map(str, years))})
            GROUP BY scenario, model_year
            ORDER BY scenario, model_year
            """
        # Execute query and return DataFrame
        print(sql)
        return self.db.execute(sql).df()

    def get_annual_peak_demand(
            self,
            scenarios: list[str] | None = None,
            years: list[int] | None = None,
            group_by: ConsumptionBreakdown | None = None,
    ) -> pd.DataFrame:
        """Queries the peak annual consumption for each scenario. If group_by is specified,
        uses the peak timestamp to look up corresponding End Use or Sector values.

        Parameters
        ----------
        years : list[int], optional
            Valid projection years for the opened project. If None, uses all projection years.
        group_by : ConsumptionBreakdown, optional
            Optionally breakdown by Sector and end Use. If None, uses total.
        scenarios : list[str], optional
            Optional list of scenarios to filter by. If None, uses all scenarios available.

        Returns
        -------
        pd.DataFrame
            DataFrame with peak demand values in tall format.

            Columns:
            - scenario: str, scenario name
            - year: int, projection year
            - sector/end_use: str, breakdown category (if group_by specified)
            - value: float, peak demand value in MW

        Examples
        --------
        >>> client = APIClient(path_or_conn)
        >>> # Get peak demand for all scenarios and years (no breakdown)
        >>> df = client.get_annual_peak_demand()

        | scenario    | year | value |
        |-------------|------|-------|
        | baseline    | 2025 | 5500  |
        | baseline    | 2030 | 5900  |
        | high_growth | 2025 | 6000  |
        | high_growth | 2030 | 6500  |

        >>> # Get peak demand by sector for specific scenarios
        >>> df = client.get_annual_peak_demand(
        ...     scenarios=["baseline", "high_growth"],
        ...     group_by="Sector"
        ... )

        | scenario    | year | sector      | value |
        |-------------|------|-------------|-------|
        | baseline    | 2025 | Commercial  | 1500  |
        | baseline    | 2025 | Industrial  | 2200  |
        | baseline    | 2025 | Residential | 1800  |
        | baseline    | 2030 | Commercial  | 1650  |
        | high_growth | 2025 | Commercial  | 1600  |
        """
        if years is None:
            years = self.years
        if scenarios is None:
            scenarios = self.scenarios

        # Validate inputs
        self._validate_scenarios(scenarios)
        self._validate_years(years)

        if group_by:
            if group_by == "End Use":
                group_col = "metric"
            else:  # group_by == "Sector"
                group_col = "sector"
            # Find peak hours and get breakdown values at those hours
            sql = f"""
            WITH peak_hours AS (
                SELECT
                    scenario,
                    model_year as year,
                    timestamp,
                    ROW_NUMBER() OVER (PARTITION BY scenario, model_year ORDER BY total_demand DESC) as rn
                FROM (
                    SELECT
                        scenario,
                        model_year,
                        timestamp,
                        SUM(value) as total_demand
                    FROM {self.energy_proj_table}
                    WHERE geography = '{self.project_country}'
                    AND scenario IN ('{"','".join(scenarios)}')
                    AND model_year IN ({','.join(map(str, years))})
                    GROUP BY scenario, model_year, timestamp
                ) totals
            )
            SELECT
                t.scenario,
                t.model_year as year,
                t.{group_col},
                t.value
            FROM {self.energy_proj_table} t
            INNER JOIN peak_hours p ON
                t.scenario = p.scenario
                AND t.model_year = p.year
                AND t.timestamp = p.timestamp
                AND p.rn = 1
            WHERE t.geography = '{self.project_country}'
            AND t.scenario IN ('{"','".join(scenarios)}')
            AND t.model_year IN ({','.join(map(str, years))})
            ORDER BY t.scenario, t.model_year, t.{group_col}
            """
        else:
            # Just get peak totals without breakdown
            sql = f"""
            SELECT
                scenario,
                model_year as year,
                MAX(total_demand) as value
            FROM (
                SELECT
                    scenario,
                    model_year,
                    timestamp,
                    SUM(value) as total_demand
                FROM {self.energy_proj_table}
                WHERE geography = '{self.project_country}'
                AND scenario IN ('{"','".join(scenarios)}')
                AND model_year IN ({','.join(map(str, years))})
                GROUP BY scenario, model_year, timestamp
            ) totals
            GROUP BY scenario, model_year
            ORDER BY scenario, model_year
            """

        # Execute query and return DataFrame
        return self.db.execute(sql).df()

    # TODO, needs a scenario as an input
    # Need an asset table to say "for this asset, this scenario, use this gdp table"
    def get_secondary_metric(
            self,
            scenario: str,
            metric: SecondaryMetric,
            years: list[int] | None = None
            ) -> pd.DataFrame:
        """
        Queries the database for the secondary metric to overlay against a particular plot on the secondary axis

        !!!Must be able to handle multiple overrides of a particular metric to differentiate between scenarios!!!

        Parameters
        ----------
        scenario : str
            A valid scenario for the project.
        metric : SecondaryMetric
            The secondary metric to query.
        years : list[int], optional
            A list of valid model years to filter by. Uses all model years if None specified.

        Returns
        -------
        pd.DataFrame
            DataFrame with secondary metric values.

            Columns:
            - year: int, model year
            - value: float, metric value for the specified scenario and metric type

        Examples
        --------
        >>> client = APIClient(path_or_conn)
        >>> df = client.get_secondary_metric("baseline", "GDP", [2025, 2030, 2035])

        | year | value |
        |------|-------|
        | 2025 | 1250.5|
        | 2030 | 1380.2|
        | 2035 | 1520.8|
        """
        if years is None:
            years = self.years

        # Validate inputs
        self._validate_scenarios([scenario])
        self._validate_years(years)

        # Placeholder implementation
        return NotImplementedError

    def get_load_duration_curve(
            self,
            years: int | list[int] | None = None,
            scenarios: list[str] | None = None,
    ) -> pd.DataFrame:
        """Gets the load duration curve for each scenario or year

        Parameters
        ----------
        years : int | list[int], optional
            A valid year or list of years for the given project. If None, uses first year.
        scenarios : list[str], optional
            List of scenarios to filter by. If None, uses all scenarios.

        Returns
        -------
        pd.DataFrame
            DataFrame with load duration curve data.

            Columns:
            - {scenario_name} or {year}: float, demand values sorted from highest to lowest
              for each scenario (if multiple scenarios) or year (if multiple years)

            Index: row number (0 to 8759 for hourly data)

        Raises
        ------
        ValueError
            If both years and scenarios are lists with more than one item

        Examples
        --------
        >>> client = APIClient(path_or_conn)
        >>> # Single year, multiple scenarios
        >>> df = client.get_load_duration_curve(2030, ["baseline", "high_growth"])
        >>> # Multiple years, single scenario
        >>> df = client.get_load_duration_curve([2025, 2030], ["baseline"])
        >>> # Single year, single scenario
        >>> df = client.get_load_duration_curve(2030, ["baseline"])
        """
        # Handle defaults
        if years is None:
            years = [self.years[0]]  # Use first year as default
        elif isinstance(years, int):
            years = [years]

        if scenarios is None:
            scenarios = self.scenarios

        # Validate that we don't have multiple years AND multiple scenarios
        if len(years) > 1 and len(scenarios) > 1:
            raise ValueError("Cannot specify multiple years and multiple scenarios simultaneously. "
                           "Please specify either multiple years with a single scenario, "
                           "or multiple scenarios with a single year.")

        # Validate inputs
        self._validate_scenarios(scenarios)
        self._validate_years(years)

        # Determine what we're pivoting on
        if len(years) > 1:
            # Multiple years, single scenario - pivot on year
            pivot_cols = [str(year) for year in years]
            sql = f"""
            WITH hourly_totals AS (
                SELECT model_year as year, timestamp, SUM(value) as total_demand
                FROM {self.energy_proj_table}
                WHERE geography = '{self.project_country}'
                AND model_year IN ({','.join(map(str, years))})
                AND scenario = '{scenarios[0]}'
                GROUP BY model_year, timestamp
            )
            SELECT {', '.join([f'"{col}"' for col in pivot_cols])}
            FROM hourly_totals
            PIVOT (
                SUM(total_demand) FOR year IN ({', '.join(map(str, years))})
            )
            """
        else:
            # Single year, multiple scenarios - pivot on scenario
            pivot_cols = scenarios
            sql = f"""
            WITH hourly_totals AS (
                SELECT scenario, timestamp, SUM(value) as total_demand
                FROM {self.energy_proj_table}
                WHERE geography = '{self.project_country}'
                AND model_year = {years[0]}
                AND scenario IN ('{"','".join(scenarios)}')
                GROUP BY scenario, timestamp
            )
            SELECT {', '.join([f'"{col}"' for col in pivot_cols])}
            FROM hourly_totals
            PIVOT (
                SUM(total_demand) FOR scenario IN ('{"','".join(scenarios)}')
            )
            """

        df = self.db.execute(sql).df()

        # Sort each column from highest to lowest
        for col in pivot_cols:
            if col in df.columns:
                df[col] = df[col].sort_values(ascending=False).values

        # Reset index to get row numbers starting from 0
        result_df = df.reset_index(drop=True)

        return result_df


    def get_scenario_summary(self, scenario: str, year: int) -> dict[str, float]:
        """
        Parameters
        ----------
        scenario : str
            A valid scenario from the project.
        year : int
            The projection year to get the summary.

        Returns
        -------
        dict[str, float]
            Dictionary of KPI metrics with metric names as keys and values as floats.

            Keys:
            - TOTAL_CONSUMPTION: float, total electricity consumption (TWh)
            - PERC_GROWTH: float, percentage growth from base year
            - PEAK_DMD: float, peak demand (MW)
            - Additional KPIs to be defined

        Examples
        --------
        >>> client = APIClient(path_or_conn)
        >>> summary = client.get_scenario_summary("baseline", 2030)
        >>> print(summary)
        {
            'TOTAL_CONSUMPTION': 45.2,
            'PERC_GROWTH': 12.5,
            'PEAK_DMD': 5500.0
        }
        """
        # Validate inputs
        self._validate_scenarios([scenario])
        self._validate_years([year])

        # Placeholder implementation
        return {
            'TOTAL_CONSUMPTION': 0.0,
            'PERC_GROWTH': 0.0,
            'PEAK_DMD': 0.0
        }

    def get_weather_metric(
        self,
        scenario: str,
        year: int,
        wvar: WeatherVar,
        resample: ResampleOptions | None = None,
        timegroup: TimeGroup | None = None
    ) -> pd.DataFrame:
        """
        Gets the weather timeseries data to use as a secondary axis. Optionally Resample to Daily or weekly mean

        Parameters
        ----------
        scenario : str
            The scenario specific weather source data
        year : int
            The valid model year to choose for the weather metric (temperature or humidity)
        wvar : WeatherVar
            The weather variable to choose
        resample : ResampleOptions, optional
            Resampling option for the data
        timegroup : TimeGroup, optional
            Time grouping option

        Returns
        -------
        pd.DataFrame
            Pandas DataFrame with weather values

            Columns:
                - datetime: Datetime64, datetime or time period depending on resample option
                - value: float,  weather metric values (temperature in °C or humidity in %)

        Examples
        --------
        >>> client = APIClient(path_or_conn)
        >>> weather = client.get_weather_metric("baseline", 2030, "Temperature", "Daily Mean")
        >>> print(weather.head())

        |  datetime  | value |
        |------------|-------|
        | 2030-01-01 |  5.2  |
        | 2030-01-02 |  6.1  |
        | 2030-01-03 |  4.8  |
        | 2030-01-04 |  7.3  |
        | 2030-01-05 |  8.9  |
        """
        # Validate inputs
        self._validate_scenarios([scenario])
        self._validate_years([year])

        # Placeholder implementation
        return pd.DataFrame({'datetime': pd.date_range(f'{year}-01-01', periods=365), 'value': [0.0] * 365})


    # NOTE we don't restrict the user to two model years here in case they use the api outside of the UI.
    # NOTE for weekly mean, depending on the year, the weekends will not be at the start or end of the week.
    def get_timeseries_comparison(
        self,
        scenario: str,
        years: int | list[int],
        group_by: ConsumptionBreakdown | None = None,
        resample: ResampleOptions = "Daily Mean",
    ) -> pd.DataFrame:
        """
        User selects 1 or more than model years. Returns tall format data with time period information.

        Parameters
        ----------
        scenario : str
            A valid scenario for the project.
        years : Union[int, list[int]]
            1 or 2 model years to view on the same chart.
        group_by : ConsumptionBreakdown
            The load broken down by sector or end use.
        resample : ResampleOptions, optional
            Resampling option for the data

        Returns
        -------
        pd.DataFrame
            DataFrame with electricity consumption timeseries data in tall format.

            Columns:
            - scenario: str, scenario name
            - year: int, projection year
            - time_period: int, day/week of year (1-365 for daily, 1-52 for weekly)
            - sector/end_use: str, breakdown category (if group_by specified)
            - value: float, consumption value

        Examples
        --------
        >>> client = APIClient(path_or_conn)
        >>> # With group_by specified
        >>> df = client.get_timeseries_comparison("baseline", [2025, 2030], "Sector")

        | scenario | year | time_period | sector      | value  |
        |----------|------|-------------|-------------|--------|
        | baseline | 2025 | 1           | Commercial  | 1250.5 |
        | baseline | 2025 | 1           | Industrial  | 2100.3 |
        | baseline | 2025 | 1           | Residential | 1800.7 |
        | baseline | 2025 | 2           | Commercial  | 1245.8 |
        | baseline | 2030 | 1           | Commercial  | 1380.2 |

        >>> # Without group_by
        >>> df = client.get_timeseries_comparison("baseline", [2025, 2030])

        | scenario | year | time_period | value  |
        |----------|------|-------------|--------|
        | baseline | 2025 | 1           | 5150.5 |
        | baseline | 2025 | 2           | 5136.2 |
        | baseline | 2030 | 1           | 5675.4 |
        | baseline | 2030 | 2           | 5666.5 |
        """

        if isinstance(years, int):
            years = [years]

        # Validate inputs
        self._validate_scenarios([scenario])
        self._validate_years(years)

        # Determine time period calculation based on resample option
        if resample == "Daily Mean":
            time_period_calc = "FLOOR(EXTRACT(DOY FROM timestamp)) + 1"
        elif resample == "Weekly Mean":
            time_period_calc = "FLOOR((EXTRACT(DOY FROM timestamp) - 1) / 7) + 1"
        else:
            raise ValueError(f"Invalid resample option: {resample}")

        if group_by:
            if group_by == "End Use":
                group_col = "metric"
            else:  # group_by == "Sector"
                group_col = "sector"
            sql = f"""
            SELECT
                scenario,
                model_year as year,
                {time_period_calc} as time_period,
                {group_col},
                AVG(value) as value
            FROM {self.energy_proj_table}
            WHERE geography = '{self.project_country}'
                AND scenario = '{scenario}'
                AND model_year IN ({','.join(map(str, years))})
            GROUP BY scenario, model_year, {time_period_calc}, {group_col}
            ORDER BY scenario, model_year, time_period, {group_col}
            """
        else:
            sql = f"""
            SELECT
                scenario,
                model_year as year,
                {time_period_calc} as time_period,
                SUM(value) as value
            FROM {self.energy_proj_table}
            WHERE geography = '{self.project_country}'
                AND scenario = '{scenario}'
                AND model_year IN ({','.join(map(str, years))})
            GROUP BY scenario, model_year, {time_period_calc}
            ORDER BY scenario, model_year, time_period
            """

        return self.db.execute(sql).df()

    def get_seasonal_load_lines(
        self,
        scenario: str,
        years: int | list[int] | None = None,
        group_by: TimeGroup = "Seasonal",
        agg: TimeGroupAgg = "Average Day",
    ) -> pd.DataFrame:
        """
        Parameters
        ----------
        scenario : str
            A valid scenario within the project.
        group_by : TimeGroup
            Seasonal, Weekday/Weekend, or Both.
        agg : TimeGroupAgg
            How to aggregate each hour of the day.
        year : Union[int, list[int]], optional
            A single or list of valid model years.

        Returns
        -------
        pd.DataFrame
            DataFrame with seasonal load line data in tall format.

            Columns:
            - scenario: str, scenario name
            - year: int, projection year
            - season: str, season name (Winter, Spring, Summer, Fall) - if group_by includes "Seasonal"
            - day_type: str, day type (Weekday, Weekend) - if group_by includes "Weekday/Weekend"
            - hour_of_day: int, hour of day (0-23)
            - value: float, aggregated load value

        Examples
        --------
        >>> client = APIClient(path_or_conn)
        >>> # Seasonal grouping only
        >>> df = client.get_seasonal_load_lines("baseline", [2025, 2030], "Seasonal", "Average Day")

        | scenario | year | season | hour_of_day | value  |
        |----------|------|--------|-------------|--------|
        | baseline | 2025 | Winter | 0           | 3200.5 |
        | baseline | 2025 | Winter | 1           | 3100.2 |
        | baseline | 2025 | Winter | 2           | 3050.8 |
        | baseline | 2025 | Spring | 0           | 2800.3 |
        | baseline | 2030 | Winter | 0           | 3450.2 |

        >>> # Both seasonal and weekday/weekend grouping
        >>> df = client.get_seasonal_load_lines("baseline", [2025], "Seasonal and Weekday/Weekend", "Average Day")

        | scenario | year | season | day_type | hour_of_day | value  |
        |----------|------|--------|----------|-------------|--------|
        | baseline | 2025 | Winter | Weekday  | 0           | 3400.5 |
        | baseline | 2025 | Winter | Weekday  | 1           | 3350.2 |
        | baseline | 2025 | Winter | Weekend  | 0           | 3000.3 |
        | baseline | 2025 | Spring | Weekday  | 0           | 2900.7 |
        """
        if years is None:
            years = self.years
        if isinstance(years, int):
            years = [years]

        # Validate inputs
        self._validate_scenarios([scenario])
        self._validate_years(years)

        # Build the select and group by clauses - calculate hour of year and hour of day
        hour_of_year_expr = f"EXTRACT(DOY FROM timestamp) * 24 + EXTRACT(HOUR FROM timestamp) - 24"
        hour_of_day_expr = "EXTRACT(HOUR FROM timestamp)"

        select_cols = ["scenario", "model_year as year", f"{hour_of_day_expr} as hour_of_day"]
        group_by_cols = ["scenario", "model_year", f"{hour_of_day_expr}"]

        # Add seasonal grouping if needed
        if "Seasonal" in group_by:
            season_case = _generate_season_case_statement(hour_of_year_expr)
            select_cols.append(f"({season_case}) as season")
            group_by_cols.append(f"({season_case})")

        # Add weekday/weekend grouping if needed
        if "Weekday/Weekend" in group_by:
            weekday_case = _generate_weekday_weekend_case_statement(hour_of_year_expr)
            select_cols.append(f"({weekday_case}) as day_type")
            group_by_cols.append(f"({weekday_case})")

        # Determine aggregation function based on agg parameter
        if agg == "Average Day":
            agg_func = "AVG"
        elif agg == "Peak Day":
            agg_func = "MAX"
        elif agg == "Minimum Day":
            agg_func = "MIN"
        elif agg == "Median Day":
            agg_func = "MEDIAN"
        else:
            raise ValueError(f"Invalid aggregation option: {agg}")

        # Build the SQL query - simplified without CTE
        select_clause = ", ".join(select_cols)
        group_by_clause = ", ".join(group_by_cols)

        # Build ORDER BY clause using only the select column aliases/names
        order_cols = ["scenario", "year"]
        if "Seasonal" in group_by:
            order_cols.append("season")
        if "Weekday/Weekend" in group_by:
            order_cols.append("day_type")
        order_cols.append("hour_of_day")
        sql = f"""
        SELECT
            {select_clause},
            {agg_func}(value) as value
        FROM {self.energy_proj_table}
        WHERE geography = '{self.project_country}'
            AND scenario = '{scenario}'
            AND model_year IN ({','.join(map(str, years))})
        GROUP BY {group_by_clause}
        ORDER BY {order_cols}
        """

        return self.db.execute(sql).df()

    def get_seasonal_load_area(
        self,
        scenario: str,
        year: int,
        group_by: TimeGroup = "Seasonal",
        agg: TimeGroupAgg = "Average Day",
        breakdown: ConsumptionBreakdown | None = None
    ) -> pd.DataFrame:
        """
        Get seasonal load area data for a single year with optional breakdown by sector/end_use.

        Parameters
        ----------
        scenario : str
            A valid scenario within the project.
        year : int
            A single valid model year.
        group_by : TimeGroup
            Seasonal, Weekday/Weekend, or Both.
        agg : TimeGroupAgg
            How to aggregate each hour of the day.
        breakdown : ConsumptionBreakdown, optional
            Optional breakdown by Sector or End Use.

        Returns
        -------
        pd.DataFrame
            DataFrame with seasonal load area data in tall format.

            Columns:
            - scenario: str, scenario name
            - year: int, projection year
            - season: str, season name (Winter, Spring, Summer, Fall) - if group_by includes "Seasonal"
            - day_type: str, day type (Weekday, Weekend) - if group_by includes "Weekday/Weekend"
            - hour_of_day: int, hour of day (0-23)
            - sector/end_use: str, breakdown category (if breakdown specified)
            - value: float, aggregated load value

        Examples
        --------
        >>> client = APIClient(path_or_conn)
        >>> df = client.get_seasonal_load_area("baseline", 2030)

        | scenario    | year | season | hour_of_day | value |
        |-------------|------|--------|-------------|-------|
        | baseline    | 2030 | Winter | 0           | 3400.5|
        | baseline    | 2030 | Winter | 1           | 3350.2|
        | baseline    | 2030 | Spring | 0           | 2900.7|
        | baseline    | 2030 | Spring | 1           | 2850.3|

        >>> df = client.get_seasonal_load_area("baseline", 2030, breakdown="Sector")

        | scenario    | year | season | hour_of_day | sector      | value |
        |-------------|------|--------|-------------|-------------|-------|
        | baseline    | 2030 | Winter | 0           | Commercial  | 1200.5|
        | baseline    | 2030 | Winter | 0           | Industrial  | 1500.2|
        | baseline    | 2030 | Winter | 0           | Residential | 1700.8|
        | baseline    | 2030 | Spring | 0           | Commercial  | 1300.7|
        | baseline    | 2030 | Spring | 0           | Industrial  | 1600.3|
        """
        # Validate inputs
        self._validate_scenarios([scenario])
        self._validate_years([year])

        # Build the select and group by clauses - calculate hour of year and hour of day
        hour_of_year_expr = f"EXTRACT(DOY FROM timestamp) * 24 + EXTRACT(HOUR FROM timestamp) - 24"
        hour_of_day_expr = "EXTRACT(HOUR FROM timestamp)"

        select_cols = ["scenario", "model_year as year", f"{hour_of_day_expr} as hour_of_day"]
        group_by_cols = ["scenario", "model_year", f"{hour_of_day_expr}"]

        # Add breakdown column if specified
        if breakdown:
            if breakdown == "End Use":
                breakdown_col = "metric"
            else:  # breakdown == "Sector"
                breakdown_col = "sector"
            select_cols.append(breakdown_col)
            group_by_cols.append(breakdown_col)

        # Add seasonal grouping if needed
        if "Seasonal" in group_by:
            season_case = _generate_season_case_statement(hour_of_year_expr)
            select_cols.append(f"({season_case}) as season")
            group_by_cols.append(f"({season_case})")

        # Add weekday/weekend grouping if needed
        if "Weekday/Weekend" in group_by:
            weekday_case = _generate_weekday_weekend_case_statement(hour_of_year_expr)
            select_cols.append(f"({weekday_case}) as day_type")
            group_by_cols.append(f"({weekday_case})")

        # Determine aggregation function based on agg parameter
        if agg == "Average Day":
            agg_func = "AVG"
        elif agg == "Peak Day":
            agg_func = "MAX"
        elif agg == "Minimum Day":
            agg_func = "MIN"
        elif agg == "Median Day":
            agg_func = "MEDIAN"
        else:
            raise ValueError(f"Invalid aggregation option: {agg}")

        # Build the SQL query
        select_clause = ", ".join(select_cols)
        group_by_clause = ", ".join(group_by_cols)

        # Build ORDER BY clause
        order_cols = ["scenario", "year"]
        if "Seasonal" in group_by:
            order_cols.append("season")
        if "Weekday/Weekend" in group_by:
            order_cols.append("day_type")
        order_cols.append("hour_of_day")
        if breakdown:
            order_cols.append(breakdown_col)
        order_by_clause = ", ".join(order_cols)

        sql = f"""
        SELECT
            {select_clause},
            {agg_func}(value) as value
        FROM {self.energy_proj_table}
        WHERE geography = '{self.project_country}'
            AND scenario = '{scenario}'
            AND model_year = {year}
        GROUP BY {group_by_clause}
        ORDER BY {order_by_clause}
        """

        return self.db.execute(sql).df()

