from __future__ import annotations

from pathlib import Path

"""
STRIDE UI Data API

This module provides a unified interface for querying electricity load and demand data
from a DuckDB database. The API offers methods
for retrieving annual consumption metrics, peak demand analysis, load duration curves,
time series comparisons, seasonal load patterns, and secondary metrics like economic
indicators and weather data.

Key Features:
- Support for scenario comparison and breakdown analysis
- Flexible time aggregation and grouping options
- Integration with secondary metrics (GDP, population, weather, etc.)

"""

from typing import Any

import pandas as pd
from loguru import logger

from stride.project import Project

from .utils import (
    ConsumptionBreakdown,
    ResampleOptions,
    SecondaryMetric,
    TimeGroup,
    TimeGroupAgg,
    WeatherVar,
    build_seasonal_query,
)

# TODO
# Secondary metric queries (GDP per capita is slightly different.)
# Weather: Currently only BAIT (Building-Adjusted Internal Temperature) is available via weather_bait_daily.


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
    - Time series data with flexible resampling and grouping
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
    ...     scenarios=["baseline", "high_growth"], group_by="Sector"
    ... )
    """

    _instance = None

    def __new__(
        cls,
        project: Project | None = None,
    ) -> APIClient:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        project: Project,
    ):
        # Check if we're switching to a different project
        if hasattr(self, "_initialized") and self._initialized:
            # Compare resolved absolute paths to handle relative vs absolute
            current_path = str(Path(self.project.path).resolve())
            new_path = str(Path(project.path).resolve())
            if current_path != new_path:
                # Switching projects - update project and clear cached state
                self.project = project
                self.project_country = self.project.config.country
                self.refresh_metadata()
            return

        # First-time initialization
        self.project = project
        self.energy_proj_table = "energy_projection"
        self.project_country = self.project.config.country

        self._years: list[int] | None = None
        self._scenarios: list[str] | None = None

        self._con = None

        self._initialized = True

    @property
    def db(self):
        """Return the current database connection from the project."""
        return self._con if self._con is not None else self.project.con

    @db.setter
    def db(self, connection):
        """Set the database connection on the project (used for testing)."""
        self._con = connection

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

    def _get_scenario_order_clause(self, table_alias: str = "") -> str:
        """
        Generate SQL CASE statement to order scenarios by project config order.

        Parameters
        ----------
        table_alias : str, optional
            Table alias to use (e.g., "t" for "t.scenario"), by default ""

        Returns
        -------
        str
            SQL CASE expression for ordering scenarios
        """
        if not self.scenarios:
            col_name = f"{table_alias}.scenario" if table_alias else "scenario"
            return col_name

        # Build CASE statement: CASE WHEN scenario='first' THEN 0 WHEN scenario='second' THEN 1 ...
        col_name = f"{table_alias}.scenario" if table_alias else "scenario"
        cases = [f"WHEN {col_name}='{s}' THEN {i}" for i, s in enumerate(self.scenarios)]
        return f"CASE {' '.join(cases)} ELSE 999 END"

    def get_unique_sectors(self) -> list[str]:
        """
        Get unique sectors from the energy projection table.

        Returns
        -------
        list[str]
            Sorted list of unique sectors from the database
        """
        sql = """
        SELECT DISTINCT sector
        FROM energy_projection
        WHERE geography = ?
        ORDER BY sector
        """
        result = self.db.execute(sql, [self.project_country]).fetchall()
        return [row[0] for row in result]

    def get_unique_end_uses(self) -> list[str]:
        """
        Get unique end uses (metrics) from the energy projection table.

        Returns
        -------
        list[str]
            Sorted list of unique end uses/metrics from the database
        """
        sql = """
        SELECT DISTINCT metric
        FROM energy_projection
        WHERE geography = ?
        ORDER BY metric
        """
        result = self.db.execute(sql, [self.project_country]).fetchall()
        return [row[0] for row in result]

    def _fetch_years(self) -> list[int]:
        """
        Fetch years from database.

        Returns
        -------
        list[int]
            Sorted list of unique model years from the database

        Raises
        ------
        TypeError
            If model_year values in the database are not integers.
        """
        sql = """
        SELECT DISTINCT model_year as year
        FROM energy_projection
        WHERE geography = ?
        ORDER BY model_year
        """
        result = self.db.execute(sql, [self.project_country]).fetchall()
        years = [row[0] for row in result]
        if years and not isinstance(years[0], int):
            msg = (
                f"model_year column has type {type(years[0]).__name__}, expected int. "
                "This is a data pipeline bug - model_year must be an integer in the database."
            )
            raise TypeError(msg)
        return years

    def _fetch_scenarios(self) -> list[str]:
        """
        Fetch scenarios from database in project config order.

        Returns
        -------
        list[str]
            List of scenarios in the order defined in the project config
        """
        # Get scenarios from project config to preserve order
        config_scenarios = self.project.list_scenario_names()

        # Verify all config scenarios exist in database
        sql = """
        SELECT DISTINCT scenario
        FROM energy_projection
        WHERE geography = ?
        """
        result = self.db.execute(sql, [self.project_country]).fetchall()
        db_scenarios = set(row[0] for row in result)

        # Return scenarios in config order, filtering to only those in database
        return [s for s in config_scenarios if s in db_scenarios]

    def _validate_scenarios(self, scenarios: list[str]) -> None:
        """
        Validate that all provided scenarios exist in the database.

        Parameters
        ----------
        scenarios : list[str]
            List of scenario names to validate

        Raises
        ------
        ValueError
            If any scenario in the list is not found in the database
        """
        if not scenarios:
            return

        valid_scenarios = set(self.scenarios)
        invalid_scenarios = [s for s in scenarios if s not in valid_scenarios]

        if invalid_scenarios:
            err = f"Invalid scenarios: {invalid_scenarios}. Valid scenarios are: {list(valid_scenarios)}"
            raise ValueError(err)

    def _validate_years(self, years: list[int]) -> None:
        """
        Validate that all provided years exist in the database.

        Parameters
        ----------
        years : list[int]
            List of years to validate

        Raises
        ------
        ValueError
            If any year in the list is not found in the database
        """
        if not years:
            return

        valid_years = set(self.years)
        invalid_years = [y for y in years if y not in valid_years]

        if invalid_years:
            err = f"Invalid years: {invalid_years}. Valid years are: {list(valid_years)}"
            raise ValueError(err)

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
            - value: float, consumption value in MWh

        Examples
        --------
        >>> client = APIClient(path_or_conn)
        >>> # Get total consumption for all scenarios and years
        >>> df = client.get_annual_electricity_consumption()

        ::

          |-------------|------|-------------|-------|
          | scenario    | year | value |
          |-------------|------|-------|
          | baseline    | 2025 | 5500  |
          | baseline    | 2030 | 5900  |
          | high_growth | 2025 | 6000  |
          | high_growth | 2030 | 6500  |
          |-------------|------|-------------|-------|

        >>> # Get consumption by sector for specific scenarios
        >>> df = client.get_annual_electricity_consumption(
        ...     scenarios=["baseline", "high_growth"], group_by="Sector"
        ... )

        ::

          |-------------|------|-------------|-------|
          | scenario    | year | sector      | value |
          |-------------|------|-------------|-------|
          | baseline    | 2025 | Commercial  | 1500  |
          | baseline    | 2025 | Industrial  | 2200  |
          | baseline    | 2025 | Residential | 1800  |
          | baseline    | 2030 | Commercial  | 1650  |
          | high_growth | 2025 | Commercial  | 1600  |
          |-------------|------|-------------|-------|
        """
        logger.debug(
            f"get_annual_electricity_consumption called with: scenarios={scenarios}, years={years}, group_by={group_by}"
        )

        if years is None:
            years = self.years
        if scenarios is None:
            scenarios = self.scenarios

        # Validate inputs
        self._validate_scenarios(scenarios)
        self._validate_years(years)

        # Build SQL query based on group_by parameter
        # Convert years to strings for SQL comparison since model_year is VARCHAR
        scenario_order = self._get_scenario_order_clause()

        if group_by:
            if group_by == "End Use":
                group_col = "metric"
            else:  # group_by == "Sector"
                group_col = "sector"

            sql = f"""
            SELECT scenario, model_year as year, {group_col}, SUM(value) as value
            FROM energy_projection
            WHERE geography = ?
            AND scenario = ANY(?)
            AND model_year = ANY(?)
            GROUP BY scenario, model_year, {group_col}
            ORDER BY {scenario_order}, model_year, {group_col}
            """
            params = [self.project_country, scenarios, years]
        else:
            sql = """
            SELECT scenario, model_year as year, SUM(value) as value
            FROM energy_projection
            WHERE geography = ?
            AND scenario = ANY(?)
            AND model_year = ANY(?)
            GROUP BY scenario, model_year
            ORDER BY {scenario_order}, model_year
            """
            params = [self.project_country, scenarios, years]

        # Execute query and return DataFrame
        logger.debug(f"SQL Query:\n{sql}")
        df = self.db.execute(sql, params).df()
        logger.debug(f"Returning {len(df)} rows.")
        return df

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

        ::

          |-------------|------|-------|
          | scenario    | year | value |
          |-------------|------|-------|
          | baseline    | 2025 | 5500  |
          | baseline    | 2030 | 5900  |
          | high_growth | 2025 | 6000  |
          | high_growth | 2030 | 6500  |
          |-------------|------|-------|

        >>> # Get peak demand by sector for specific scenarios
        >>> df = client.get_annual_peak_demand(
        ...     scenarios=["baseline", "high_growth"], group_by="Sector"
        ... )

        ::

          |-------------|------|-------------|-------|
          | scenario    | year | sector      | value |
          |-------------|------|-------------|-------|
          | baseline    | 2025 | Commercial  | 1500  |
          | baseline    | 2025 | Industrial  | 2200  |
          | baseline    | 2025 | Residential | 1800  |
          | baseline    | 2030 | Commercial  | 1650  |
          | high_growth | 2025 | Commercial  | 1600  |
          |-------------|------|-------------|-------|
        """
        logger.debug(
            f"get_annual_peak_demand called with: scenarios={scenarios}, years={years}, group_by={group_by}"
        )
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
            # Use table alias 't' in ORDER BY since we have a JOIN
            scenario_order = self._get_scenario_order_clause(table_alias="t")
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
                    FROM energy_projection
                    WHERE geography = ?
                    AND scenario = ANY(?)
                    AND model_year = ANY(?)
                    GROUP BY scenario, model_year, timestamp
                ) totals
            )
            SELECT
                t.scenario,
                t.model_year as year,
                t.{group_col},
                t.value
            FROM energy_projection t
            INNER JOIN peak_hours p ON
                t.scenario = p.scenario
                AND t.model_year = p.year
                AND t.timestamp = p.timestamp
                AND p.rn = 1
            WHERE t.geography = ?
            AND t.scenario = ANY(?)
            AND t.model_year = ANY(?)
            ORDER BY {scenario_order}, t.model_year, t.{group_col}
            """
            params = [
                self.project_country,
                scenarios,
                years,
                self.project_country,
                scenarios,
                years,
            ]
        else:
            # Just get peak totals without breakdown
            scenario_order = self._get_scenario_order_clause()
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
                FROM energy_projection
                WHERE geography = ?
                AND scenario = ANY(?)
                AND model_year = ANY(?)
                GROUP BY scenario, model_year, timestamp
            ) totals
            GROUP BY scenario, model_year
            ORDER BY {scenario_order}, model_year
            """
            params = [self.project_country, scenarios, years]

        # Execute query and return DataFrame
        logger.debug(f"SQL Query:\n{sql}")
        df = self.db.execute(sql, params).df()
        logger.debug(f"Returning {len(df)} rows.")
        return df

    # TODO, needs a scenario as an input
    # Need an asset table to say "for this asset, this scenario, use this gdp table"
    def get_secondary_metric(
        self, scenario: str, metric: SecondaryMetric, years: list[int] | None = None
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

        ::

          |------|-------|
          | year | value |
          |------|-------|
          | 2025 | 1250.5|
          | 2030 | 1380.2|
          | 2035 | 1520.8|
          |------|-------|
        """
        logger.debug(
            f"get_secondary_metric called with: scenario={scenario}, metric={metric}, years={years}"
        )
        if years is None:
            years = self.years

        # Validate inputs
        self._validate_scenarios([scenario])
        self._validate_years(years)

        # Map metric names to table names
        metric_table_map = {
            "GDP": "gdp_country",
            "GDP Per Capita": "gdp_country",
            "Human Development Index": "hdi_country",
            "Population": "population_country",
            # Additional metrics can be added here as they become available
        }

        if metric not in metric_table_map:
            err = f"Metric '{metric}' is not yet supported."
            raise NotImplementedError(err)

        base_table = metric_table_map[metric]
        override_table = f"{base_table}_override"

        # Check if override table exists for this scenario
        table_exists_sql = """
        SELECT COUNT(*) as count
        FROM information_schema.tables
        WHERE table_schema = ?
        AND table_name = ?
        """
        result = self.db.execute(table_exists_sql, [scenario, override_table]).fetchone()
        has_override = result[0] > 0 if result else False

        # Use override table if it exists, otherwise use base table
        table_to_query = (
            f"{scenario}.{override_table}" if has_override else f"{scenario}.{base_table}"
        )

        # Check if the table exists before querying
        table_name_only = override_table if has_override else base_table
        result = self.db.execute(table_exists_sql, [scenario, table_name_only]).fetchone()
        table_exists = result[0] > 0 if result else False

        if not table_exists:
            err = f"Table not available for {metric} in scenario '{scenario}'"
            raise ValueError(err)

        logger.debug(f"Querying table: {table_to_query} (has_override={has_override})")

        # Query the appropriate table
        sql = """
        SELECT model_year as year, value
        FROM {table}
        WHERE geography = ?
        AND model_year = ANY(?)
        ORDER BY model_year
        """.format(table=table_to_query)

        params = [self.project_country, years]

        # Execute query and return DataFrame
        logger.debug(f"SQL Query:\n{sql}")
        try:
            df = self.db.execute(sql, params).df()
        except Exception as e:
            err = f"Error querying {metric} table for scenario '{scenario}': {str(e)}"
            raise ValueError(err) from e

        # For GDP Per Capita, divide GDP by population and convert to USD/person
        if metric == "GDP Per Capita":
            pop_df = self.get_secondary_metric(scenario, "Population", years)
            if not pop_df.empty and not df.empty:
                df = df.merge(pop_df, on="year", suffixes=("_gdp", "_pop"))
                # GDP is in billion USD-2024, so multiply by 1e9 to get USD-2024/person
                df["value"] = (df["value_gdp"] * 1e9) / df["value_pop"]
                df = df[["year", "value"]]

        logger.debug(f"Returning {len(df)} rows.")
        return df

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

        logger.debug(f"get_load_duration_curve called with: years={years}, scenarios={scenarios}")
        # Handle defaults
        if years is None:
            years = [self.years[0]]  # Use first year as default
        elif isinstance(years, int):
            years = [years]

        if scenarios is None:
            scenarios = self.scenarios

        # Validate that we don't have multiple years AND multiple scenarios
        if len(years) > 1 and len(scenarios) > 1:
            msg = """
            Cannot specify multiple years and multiple scenarios simultaneously.
            Please specify either multiple years with a single scenario,
            or multiple scenarios with a single year.
            """
            raise ValueError(msg)

        # Validate inputs
        self._validate_scenarios(scenarios)
        self._validate_years(years)

        # Determine what we're pivoting on
        if len(years) > 1:
            # Multiple years, single scenario - pivot on year
            pivot_cols = [str(year) for year in years]
            year_pivot_list = ",".join([str(year) for year in years])

            sql = f"""
            WITH hourly_totals AS (
                SELECT model_year as year, timestamp, SUM(value) as total_demand
                FROM energy_projection
                WHERE geography = ?
                AND model_year = ANY(?)
                AND scenario = ?
                GROUP BY model_year, timestamp
            )
            SELECT {", ".join([f'"{col}"' for col in pivot_cols])}
            FROM hourly_totals
            PIVOT (
                SUM(total_demand) FOR year IN ({year_pivot_list})
            )
            """
            params: list[Any] = [self.project_country, years, scenarios[0]]
        else:
            # Single year, multiple scenarios - pivot on scenario
            # Order scenarios according to project config order
            pivot_cols = [s for s in self.scenarios if s in scenarios]
            scenario_pivot_list = ",".join([f"'{s}'" for s in pivot_cols])

            sql = f"""
            WITH hourly_totals AS (
                SELECT scenario, timestamp, SUM(value) as total_demand
                FROM energy_projection
                WHERE geography = ?
                AND model_year = ?
                AND scenario = ANY(?)
                GROUP BY scenario, timestamp
            )
            SELECT {", ".join([f'"{col}"' for col in pivot_cols])}
            FROM hourly_totals
            PIVOT (
                SUM(total_demand) FOR scenario IN ({scenario_pivot_list})
            )
            """
            params = [self.project_country, years[0], scenarios]

        logger.debug(f"SQL Query:\n{sql}")
        df = self.db.execute(sql, params).df()

        # Sort each column from highest to lowest
        for col in pivot_cols:
            if col in df.columns:
                df[col] = df[col].sort_values(ascending=False).values

        # Reset index to get row numbers starting from 0
        result_df = df.reset_index(drop=True)

        logger.debug(f"Returning {len(result_df)} rows.")
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
            - TOTAL_CONSUMPTION: float, total electricity consumption (MWh)
            - PERCENT_GROWTH: float, percentage growth from base year
            - PEAK_DEMAND: float, peak demand (MW)
            - Additional KPIs to be defined

        Examples
        --------
        >>> client = APIClient(path_or_conn)
        >>> summary = client.get_scenario_summary("baseline", 2030)
        >>> print(summary)
        {
            'TOTAL_CONSUMPTION': 45.2,
            'PERCENT_GROWTH': 12.5,
            'PEAK_DEMAND': 5500.0
        }
        """
        logger.debug(f"get_scenario_summary called with: scenario={scenario}, year={year}")
        # Validate inputs
        self._validate_scenarios([scenario])
        self._validate_years([year])

        # Placeholder implementation
        logger.warning("get_scenario_summary is not implemented.")
        return {"TOTAL_CONSUMPTION": 0.0, "PERCENT_GROWTH": 0.0, "PEAK_DEMAND": 0.0}

    def get_weather_metric(
        self,
        scenario: str,
        year: int,
        wvar: WeatherVar,
        resample: ResampleOptions,
        timegroup: TimeGroup | None = None,
    ) -> pd.DataFrame:
        """
        Gets the weather time series data to use as a secondary axis. Optionally Resample to Daily or weekly mean

        Parameters
        ----------
        scenario : str
            The scenario specific weather source data
        year : int
            The valid model year to choose for the weather metric
        wvar : WeatherVar
            The weather variable to choose (currently only "BAIT" is supported)
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
                - value: float, BAIT (Balance Point Adjusted Integrated Temperature) values

        Examples
        --------
        >>> client = APIClient(path_or_conn)
        >>> weather = client.get_weather_metric("baseline", 2030, "BAIT", "Daily Mean")
        >>> print(weather.head())

        ::

          |------------|-------|
          |  datetime  | value |
          |------------|-------|
          | 2030-01-01 |  5.2  |
          | 2030-01-02 |  6.1  |
          | 2030-01-03 |  4.8  |
          | 2030-01-04 |  7.3  |
          | 2030-01-05 |  8.9  |
          |------------|-------|
        """
        logger.debug(
            f"get_weather_metric called with: scenario={scenario}, year={year}, wvar={wvar}, resample={resample}, timegroup={timegroup}"
        )
        # Validate inputs
        self._validate_scenarios([scenario])
        self._validate_years([year])

        # Map weather variable to column name
        wvar_column_map = {
            "BAIT": "bait",
            "HDD": "hdd",
            "CDD": "cdd",
        }

        if wvar not in wvar_column_map:
            err = f"Weather variable '{wvar}' is not supported. Available options: {list(wvar_column_map.keys())}"
            raise ValueError(err)

        column_name = wvar_column_map[wvar]

        # Use weather_degree_days which includes bait, hdd, and cdd
        # This is a dbt model that's created per scenario
        base_table = "weather_degree_days"
        override_table = f"{base_table}_override"

        table_exists_sql = """
        SELECT COUNT(*) as count
        FROM information_schema.tables
        WHERE table_schema = ?
        AND table_name = ?
        """

        # Check for override table in scenario schema
        result = self.db.execute(table_exists_sql, [scenario, override_table]).fetchone()
        has_override = result[0] > 0 if result else False

        # Use override table if it exists, otherwise use base table
        table_to_query = (
            f"{scenario}.{override_table}" if has_override else f"{scenario}.{base_table}"
        )

        # Check if the table exists before querying
        table_name_only = override_table if has_override else base_table
        result = self.db.execute(table_exists_sql, [scenario, table_name_only]).fetchone()
        table_exists = result[0] > 0 if result else False

        if not table_exists:
            err = f"Weather table '{table_name_only}' not available in schema '{scenario}'"
            raise ValueError(err)

        logger.debug(f"Querying table: {table_to_query} (has_override={has_override})")

        # Build the query based on resample option
        if resample == "Hourly":
            # Return hourly data
            # Note: Weather data uses weather_year column, not EXTRACT(YEAR FROM timestamp)
            sql = """
            SELECT timestamp as datetime, {column} as value
            FROM {table}
            WHERE geography = ?
            ORDER BY timestamp
            """.format(table=table_to_query, column=column_name)
        elif resample == "Daily Mean":
            # Aggregate to daily mean
            # Note: Weather data uses weather_year column, not EXTRACT(YEAR FROM timestamp)
            sql = """
            SELECT
                DATE_TRUNC('day', timestamp) as datetime,
                AVG({column}) as value
            FROM {table}
            WHERE geography = ?
            GROUP BY DATE_TRUNC('day', timestamp)
            ORDER BY datetime
            """.format(table=table_to_query, column=column_name)
        elif resample == "Weekly Mean":
            # Aggregate to weekly mean using day-of-year to avoid cross-year week issues
            # Week calculation: FLOOR((DOY - 1) / 7) groups days 1-7 as week 0, 8-14 as week 1, etc.
            # This matches the calculation in get_time_series_comparison() but without the +1
            # since we only use this for grouping and then take MIN(timestamp) for the x-axis
            # Note: Weather data is intensive (temperature), not extensive (energy), so we don't
            # rescale partial weeks. Temperature average is the same regardless of week length.
            # Note: Weather data uses weather_year column, not EXTRACT(YEAR FROM timestamp)
            sql = """
            SELECT
                MIN(timestamp) as datetime,
                AVG({column}) as value
            FROM {table}
            WHERE geography = ?
            GROUP BY FLOOR((EXTRACT(DOY FROM timestamp) - 1) / 7)
            ORDER BY datetime
            """.format(table=table_to_query, column=column_name)
        else:
            err = f"Resample option '{resample}' is not supported."
            raise ValueError(err)

        # Weather data is filtered by geography only (not by year, since weather_year is fixed)
        params = [self.project_country]

        # Execute query and return DataFrame
        logger.debug(f"SQL Query:\n{sql}")
        logger.debug(f"Query params: geography={self.project_country}")
        logger.debug(f"Querying table: {table_to_query}")
        try:
            df = self.db.execute(sql, params).df()
            logger.debug(f"Query returned {len(df)} rows.")
        except Exception as e:
            err = f"Error querying weather data for scenario '{scenario}': {str(e)}"
            raise ValueError(err) from e
        return df

    # NOTE we don't restrict the user to two model years here in case they use the api outside of the UI.
    # NOTE for weekly mean, depending on the year, the weekends will not be at the start or end of the week.
    def get_time_series_comparison(
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
            Resampling option for the data. Use None for raw hourly data.

        Returns
        -------
        pd.DataFrame
            DataFrame with electricity consumption time series data in tall format.

            Columns:
            - scenario: str, scenario name
            - year: int, projection year
            - time_period: int, time period (hour of year for raw data, day/week for resampled)
            - sector/end_use: str, breakdown category (if group_by specified)
            - value: float, consumption value

        Examples
        --------
        >>> client = APIClient(path_or_conn)
        >>> # Raw hourly data with group_by
        >>> df = client.get_time_series_comparison(
        ...     "baseline", [2025, 2030], "Sector", resample=None
        ... )

        ::

          |----------|------|-------------|-------------|--------|
          | scenario | year | time_period | sector      | value  |
          |----------|------|-------------|-------------|--------|
          | baseline | 2025 | 1           | Commercial  | 125.5  |
          | baseline | 2025 | 1           | Industrial  | 210.3  |
          | baseline | 2025 | 1           | Residential | 180.7  |
          | baseline | 2025 | 2           | Commercial  | 124.8  |
          |----------|------|-------------|-------------|--------|

        >>> # Resampled data with group_by specified
        >>> df = client.get_time_series_comparison("baseline", [2025, 2030], "Sector")

        ::

          |----------|------|-------------|-------------|--------|
          | scenario | year | time_period | sector      | value  |
          |----------|------|-------------|-------------|--------|
          | baseline | 2025 | 1           | Commercial  | 1250.5 |
          | baseline | 2025 | 1           | Industrial  | 2100.3 |
          | baseline | 2025 | 1           | Residential | 1800.7 |
          | baseline | 2025 | 2           | Commercial  | 1245.8 |
          | baseline | 2030 | 1           | Commercial  | 1380.2 |
          |----------|------|-------------|-------------|--------|

        >>> # Raw hourly data without group_by
        >>> df = client.get_time_series_comparison("baseline", [2025, 2030], resample=None)

        ::

          |----------|------|-------------|--------|
          | scenario | year | time_period | value  |
          |----------|------|-------------|--------|
          | baseline | 2025 | 1           | 5150.5 |
          | baseline | 2025 | 2           | 5136.2 |
          | baseline | 2030 | 1           | 5675.4 |
          | baseline | 2030 | 2           | 5666.5 |
          |----------|------|-------------|--------|
        """
        logger.debug(
            f"get_time_series_comparison called with: scenario={scenario}, years={years}, group_by={group_by}, resample={resample}"
        )

        if isinstance(years, int):
            years = [years]

        # Validate inputs
        self._validate_scenarios([scenario])
        self._validate_years(years)

        if resample == "Hourly":
            # Raw hourly data - use hour of year as time_period
            time_period_calc = (
                "ROW_NUMBER() OVER (PARTITION BY scenario, model_year ORDER BY timestamp)"
            )

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
                    value
                FROM energy_projection
                WHERE geography = ?
                    AND scenario = ?
                    AND model_year = ANY(?)
                ORDER BY scenario, model_year, timestamp, {group_col}
                """
                params: list[Any] = [self.project_country, scenario, years]
            else:
                sql = f"""
                WITH hourly_totals AS (
                    SELECT
                        scenario,
                        model_year,
                        timestamp,
                        SUM(value) as value
                    FROM energy_projection
                    WHERE geography = ?
                        AND scenario = ?
                        AND model_year = ANY(?)
                    GROUP BY scenario, model_year, timestamp
                )
                SELECT
                    scenario,
                    model_year as year,
                    {time_period_calc} as time_period,
                    value
                FROM hourly_totals
                ORDER BY scenario, model_year, timestamp
                """
                params = [self.project_country, scenario, years]
        else:
            # Resampled data (existing logic)
            # Determine time period calculation based on resample option
            if resample == "Daily Mean":
                time_period_calc = "FLOOR(EXTRACT(DOY FROM timestamp)) + 1"
            elif resample == "Weekly Mean":
                # Week calculation: FLOOR((DOY - 1) / 7) + 1 gives 1-indexed weeks
                # Days 1-7 = week 1, 8-14 = week 2, etc. This avoids DATE_TRUNC cross-year issues.
                # Same base calculation used in get_weather_metric() for consistency.
                time_period_calc = "FLOOR((EXTRACT(DOY FROM timestamp) - 1) / 7) + 1"
            else:
                err = f"Invalid resample option: {resample}"
                raise ValueError(err)

            # Note: We use AVG for both Daily Mean and Weekly Mean, so no rescaling needed.
            # Averaging is an intensive operation (value per unit time), not extensive (total),
            # so partial weeks have the same average as full weeks.

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
                FROM energy_projection
                WHERE geography = ?
                    AND scenario = ?
                    AND model_year = ANY(?)
                GROUP BY scenario, model_year, {time_period_calc}, {group_col}
                ORDER BY scenario, model_year, time_period, {group_col}
                """
                params = [self.project_country, scenario, years]
            else:
                sql = f"""
                SELECT
                    scenario,
                    model_year as year,
                    {time_period_calc} as time_period,
                    AVG(value) as value
                FROM energy_projection
                WHERE geography = ?
                    AND scenario = ?
                    AND model_year = ANY(?)
                GROUP BY scenario, model_year, {time_period_calc}
                ORDER BY scenario, model_year, time_period
                """
                params = [self.project_country, scenario, years]

        logger.debug(f"SQL Query:\n{sql}")
        df = self.db.execute(sql, params).df()
        logger.debug(f"Returning {len(df)} rows.")
        return df

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
        years : int | list[int]] | None
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
        >>> df = client.get_seasonal_load_lines(
        ...     "baseline", [2025, 2030], "Seasonal", "Average Day"
        ... )

        ::

          |----------|------|--------|-------------|--------|
          | scenario | year | season | hour_of_day | value  |
          |----------|------|--------|-------------|--------|
          | baseline | 2025 | Winter | 0           | 3200.5 |
          | baseline | 2025 | Winter | 1           | 3100.2 |
          | baseline | 2025 | Winter | 2           | 3050.8 |
          | baseline | 2025 | Spring | 0           | 2800.3 |
          | baseline | 2030 | Winter | 0           | 3450.2 |
          |----------|------|--------|-------------|--------|

        >>> # Both seasonal and weekday/weekend grouping
        >>> df = client.get_seasonal_load_lines(
        ...     "baseline", [2025], "Seasonal and Weekday/Weekend", "Average Day"
        ... )

        ::

          |----------|------|--------|----------|-------------|--------|
          | scenario | year | season | day_type | hour_of_day | value  |
          |----------|------|--------|----------|-------------|--------|
          | baseline | 2025 | Winter | Weekday  | 0           | 3400.5 |
          | baseline | 2025 | Winter | Weekday  | 1           | 3350.2 |
          | baseline | 2025 | Winter | Weekend  | 0           | 3000.3 |
          | baseline | 2025 | Spring | Weekday  | 0           | 2900.7 |
          |----------|------|--------|----------|-------------|--------|
        """
        logger.debug(
            f"get_seasonal_load_lines called with: scenario={scenario}, years={years}, group_by={group_by}, agg={agg}"
        )

        # Handle defaults and validation
        if years is None:
            years = self.years
        if isinstance(years, int):
            years = [years]

        self._validate_scenarios([scenario])
        self._validate_years(years)

        # Build and execute query using utility function
        sql, params = build_seasonal_query(
            table_name=self.energy_proj_table,
            country=self.project_country,
            scenario=scenario,
            years=years,
            group_by=group_by,
            agg=agg,
        )

        logger.debug(f"SQL Query:\n{sql}")
        df = self.db.execute(sql, params).df()
        logger.debug(f"Returning {len(df)} rows.")
        return df

    def get_seasonal_load_area(
        self,
        scenario: str,
        year: int,
        group_by: TimeGroup = "Seasonal",
        agg: TimeGroupAgg = "Average Day",
        breakdown: ConsumptionBreakdown | None = None,
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

        ::

          |-------------|------|--------|-------------|-------|
          | scenario    | year | season | hour_of_day | value |
          |-------------|------|--------|-------------|-------|
          | baseline    | 2030 | Winter | 0           | 3400.5|
          | baseline    | 2030 | Winter | 1           | 3350.2|
          | baseline    | 2030 | Spring | 0           | 2900.7|
          | baseline    | 2030 | Spring | 1           | 2850.3|
          |-------------|------|--------|-------------|-------|

        >>> df = client.get_seasonal_load_area("baseline", 2030, breakdown="Sector")

        ::

          |-------------|------|--------|-------------|-------------|-------|
          | scenario    | year | season | hour_of_day | sector      | value |
          |-------------|------|--------|-------------|-------------|-------|
          | baseline    | 2030 | Winter | 0           | Commercial  | 1200.5|
          | baseline    | 2030 | Winter | 0           | Industrial  | 1500.2|
          | baseline    | 2030 | Winter | 0           | Residential | 1700.8|
          | baseline    | 2030 | Spring | 0           | Commercial  | 1300.7|
          | baseline    | 2030 | Spring | 0           | Industrial  | 1600.3|
          |-------------|------|--------|-------------|-------------|-------|
        """
        logger.debug(
            f"get_seasonal_load_area called with: scenario={scenario}, year={year}, group_by={group_by}, agg={agg}, breakdown={breakdown}"
        )

        # Validate inputs
        self._validate_scenarios([scenario])
        self._validate_years([year])

        # Build and execute query using utility function
        sql, params = build_seasonal_query(
            table_name=self.energy_proj_table,
            country=self.project_country,
            scenario=scenario,
            years=[year],
            group_by=group_by,
            agg=agg,
            breakdown=breakdown,
        )

        logger.debug(f"SQL Query:\n{sql}")
        df = self.db.execute(sql, params).df()
        logger.debug(f"Returning {len(df)} rows.")
        return df
