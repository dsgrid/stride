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
1. We need some way of determining the valid model years. Preferably a fast lookup of the project config.
2. For secondary metrics, how do we handle different versions of table overrides (e.g. Two versions of GDP)
3. What is "Absolute Value" in the Scenario Summary Stats? (Assuming total consumption (TWh))
4. In the timeseries charts, It seems like Daily or Weekly mean should be in separate dropdown category.
5. For Comparing two timeseries, we need to handle displaying the secondary axis weather variable for both model years
6. It might be benificial to have Annual Consumption (Peak and Total) be merged under the same API.
"""

import threading
from pathlib import Path
from typing import  Literal, TYPE_CHECKING, Union
if TYPE_CHECKING:
    import pandas as pd
    import duckdb


ConsumptionBreakdown = Literal["End Use", "Sector"]
Unit = Literal["kW", "MW", "TW", "TWh"] # - ? Nice to have but not used
SecondaryMetric = Literal["GDP","GDP Per Capita","Human Development Index", "Percent EV Adoption", "Population", "Stock"]
WeatherVar = Literal["Humidity", "Temperature"]
Sectors = Literal["Commercial", "Industrial", "Residential", "Transportation", "Other"]
ChartType = Literal["Area", "Line"]
ResampleOptions = Literal["Daily Mean", "Weekly Mean"] # ? - Could be more concise by removing the word "mean"
TimeGroup = Literal["Seasonal", "Seasonal and Weekday/Weekend", "Weekday/Weekend"] # ? - Rename to something else? This corresponds to how we group days of the year.
TimeGroupAgg = Literal["Average Day", "Peak Day", "Minimum Day", "Median Day"]



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

    Examples
    --------
    >>> # Initialize with database path
    >>> client = APIClient("/path/to/database.db")
    >>>
    >>> # Subsequent calls return the same instance
    >>> same_client = APIClient()  # No parameters needed
    >>> assert client is same_client
    >>>
    >>> # Query annual consumption by sector
    >>> consumption = client.get_annual_electricity_consumption(
    ...     scenarios=["baseline", "high_growth"],
    ...     group_by="Sector"
    ... )
    >>>
    >>> # Get load duration curve for capacity analysis
    >>> ldc = client.get_load_duration_curve(year=2030)
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, path_or_conn: Union[str, Path, 'duckdb.DuckDBPyConnection'] = None):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, path_or_conn: Union[str, Path, 'duckdb.DuckDBPyConnection'] = None):
        if not hasattr(self, '_initialized'):
            if path_or_conn is None:
                raise ValueError("Database connection, path, or connection string must be provided on first initialization")

            # Handle different input types
            if isinstance(path_or_conn, str):
                # Convert string to Path and validate
                db_path = Path(path_or_conn)
                if not db_path.exists():
                    raise FileNotFoundError(f"Database file not found: {db_path}")
                if not db_path.is_file():
                    raise ValueError(f"Path is not a file: {db_path}")

                # Create DuckDB connection
                try:
                    import duckdb
                    self.db = duckdb.connect(str(db_path))
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
                    self.db = duckdb.connect(str(path_or_conn))
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

            self._initialized = True

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
        pass

    def get_scenarios(self) -> list[str]:
        """
        Returns
        -------
        list[str]
            A list of valid scenarios. Used for validating inputs into api query functions.

        Examples
        --------
        >>> client = APIClient(path_or_conn)
        >>> scenarios = client.get_scenarios()
        >>> print(scenarios)
        ['baseline', 'high_growth', 'electrification']
        """
        pass

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
            DataFrame with peak demand values.

            Columns:
            - scenario: str, scenario name
            - sector/end_use: str, breakdown category (if group_by specified)
            - {year}: float, peak demand for each year in MW

            Structure varies based on group_by parameter:
            - If group_by is None: scenario, year columns only
            - If group_by="Sector": scenario, sector, year columns
            - If group_by="End Use": scenario, end_use, year columns

        Examples
        --------
        >>> client = APIClient(path_or_conn)
        >>> # Get total consumption for all scenarios and years
        >>> df = client.get_annual_electricity_consumption()
        >>>
        >>> # Get consumption by sector for specific scenarios
        >>> df = client.get_annual_electricity_consumption(
        ...     scenarios=["baseline", "high_growth"],
        ...     group_by="Sector"
        ... )
        >>>
        >>> # Get consumption for specific years only
        >>> df = client.get_annual_electricity_consumption(
        ...     years=[2025, 2030, 2035],
        ...     group_by="End Use"
        ... )

        With sector breakdown:

        | scenario    | sector      | 2025 | 2030 | ... |
        |-------------|-------------|------|------| --- |
        | baseline    | Commercial  | 1500 | 1650 | ... |
        | baseline    | Industrial  | 2200 | 2400 | ... |
        | baseline    | Residential | 1800 | 1950 | ... |
        | high_growth | Commercial  | 1600 | 1800 | ... |

        Without breakdown (total only):

        | year        | baseline | high_growth |
        |-------------|----------|-------------|
        | 2025        | 5500     | 6000        |
        | 2030        | 5900     | 6500        |
        """
        pass

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
            DataFrame with peak demand values.

            Columns:
            - scenario: str, scenario name
            - sector/end_use: str, breakdown category (if group_by specified)
            - {year}: float, peak demand for each year in MW

            Structure varies based on group_by parameter:
            - If group_by is None: year column and scenario columns
            - If group_by="Sector": scenario, sector, year columns
            - If group_by="End Use": scenario, end_use, year columns

        Examples
        --------
        >>> client = APIClient(path_or_conn)
        >>> # Get peak demand for all scenarios and years (no breakdown)
        >>> df = client.get_annual_peak_demand()
        >>>
        >>> # Get peak demand by sector for specific scenarios
        >>> df = client.get_annual_peak_demand(
        ...     scenarios=["baseline", "high_growth"],
        ...     group_by="Sector"
        ... )
        >>>
        >>> # Get peak demand for specific years with end use breakdown
        >>> df = client.get_annual_peak_demand(
        ...     years=[2025, 2030],
        ...     group_by="End Use"
        ... )

        With sector breakdown:

        | scenario    | sector      | 2025 | 2030 |
        |-------------|-------------|------|------|
        | baseline    | Commercial  | 1500 | 1650 |
        | baseline    | Industrial  | 2200 | 2400 |
        | baseline    | Residential | 1800 | 1950 |
        | high_growth | Commercial  | 1600 | 1800 |

        Without breakdown (peak only):

        | year        | baseline | high_growth |
        |-------------|----------|-------------|
        | 2025        | 5500     | 6000        |
        | 2030        | 5900     | 6500        |
        """
        pass

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
        pass

    def get_load_duration_curve(
            self,
            year: int,
            scenarios: list[str] | None = None,  # in case we want to filter scenarios from the UI from a drop-down rather than plotly filters.
    ) -> pd.DataFrame:
        """Gets the load duration curve for each scenario

        Parameters
        ----------
        year : int
            A valid year for the given project.
        scenarios : list[str], optional
            List of scenarios to filter by

        Returns
        -------
        pd.DataFrame
            DataFrame with load duration curve data.

            Columns:
            - {scenario_name}: float, demand values sorted from highest to lowest for each scenario

            Index: row number (0 to 8759 for hourly data)

        Examples
        --------
        >>> client = APIClient(path_or_conn)
        >>> df = client.get_load_duration_curve(2030, ["baseline", "high_growth"])

        |      | baseline | high_growth |
        |------|----------|-------------|
        | 0    | 5500.2   | 5890.1      |
        | 1    | 5495.8   | 5885.3      |
        | 2    | 5490.1   | 5880.7      |
        | ...  | ...      | ...         |
        """
        pass


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
        pass


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
        pass

    # TODO The datetime columns for Sector/End Use breakdown, could be a simple integer index and
    # we create the timestamp outside of this api.
    def get_timeseries_comparison(
        self,
        scenario: str,
        years: int | list[int],
        group_by: ConsumptionBreakdown | None = None,
        resample: ResampleOptions = "Daily Mean",
    ) -> pd.DataFrame:
        """
        User selects no more than 2 model years. Returns transposed data with columns for each time period.

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
            DataFrame with electricity consumption timeseries data transposed by time period.

            When group_by is specified:
            - Index: breakdown categories (e.g., Commercial, Industrial, etc.)
            - Columns: {year}_{day/week_of_year} for each time period in each year

            When group_by is None:
            - Index: day/week of year
            - Columns: one column for each year

        Examples
        --------
        >>> client = APIClient(path_or_conn)
        >>> # With group_by specified - columns for each day of year per year
        >>> df = client.get_timeseries_comparison("baseline", [2025, 2030], "Sector")

        | {Sector/End Use} | year  | 2025-01-01 | 2025-01-02 | ... | 2025-12-30 | 2025-12-31 |
        |------------------|-------|------------|------------|-----|------------|------------|
        |    Commercial    | 2030  | 1250.5     | 1245.8     | ... | 1380.2     | 1375.5     |
        |    Industrial    | 2030  | 2100.3     | 2095.1     | ... | 2350.8     | 2345.2     |
        |    Residential   | 2030  | 1800.7     | 1795.3     | ... | 1950.4     | 1945.8     |

        >>> # Without group_by - columns for each year
        >>> df = client.get_timeseries_comparison("baseline", [2025, 2030])

        | day_of_year | 2025   | 2030   |
        |-------------|--------|--------|
        | 1           | 5150.5 | 5675.4 |
        | 2           | 5136.2 | 5666.5 |
        | ...         | ...    | ...    |
        """
        pass

    def get_seasonal_load_lines(
        self,
        scenario: str,
        years: int | list[int] | None = None,
        group_by: TimeGroup ="Seasonal",
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
            DataFrame with seasonal load line data.

            Columns:
            - season: str, season name (Winter, Spring, Summer, Fall) - if group_by includes "Seasonal"
            - day_type: str, day type (Weekday, Weekend) - if group_by includes "Weekday/Weekend"
            - year: int, model year - if multiple years specified
            - 1, 2, ..., 24: float, aggregated load values for each hour of the day

        Examples
        --------
        >>> client = APIClient(path_or_conn)
        >>> # Seasonal grouping only
        >>> df = client.get_seasonal_load_lines("baseline", "Seasonal", "Average Day", [2025, 2030])

        | season | year | 1      | 2      | 3      | ... | 23     | 24     |
        |--------|------|--------|--------|--------|-----|--------|--------|
        | Winter | 2025 | 3200.5 | 3100.2 | 3050.8 | ... | 3180.4 | 3220.1 |
        | Spring | 2025 | 2800.3 | 2750.8 | 2720.5 | ... | 2790.2 | 2810.6 |
        | Summer | 2025 | 3500.1 | 3450.5 | 3420.2 | ... | 3480.8 | 3510.3 |
        | Fall   | 2025 | 2900.7 | 2850.3 | 2820.9 | ... | 2880.5 | 2920.8 |
        | Winter | 2030 | 3450.2 | 3380.5 | 3350.1 | ... | 3430.7 | 3470.4 |

        >>> # Weekday/Weekend grouping only
        >>> df = client.get_seasonal_load_lines("baseline", "Weekday/Weekend", "Average Day", 2030)

        | day_type | year | 1      | 2      | 3      | ... | 23     | 24     |
        |----------|------|--------|--------|--------|-----|--------|--------|
        | Weekday  | 2025 | 3800.5 | 3750.2 | 3720.8 | ... | 3780.4 | 3820.1 |
        | Weekend  | 2025 | 3200.3 | 3150.8 | 3120.5 | ... | 3180.2 | 3220.6 |

        >>> # Both seasonal and weekday/weekend grouping
        >>> df = client.get_seasonal_load_lines("baseline", "Seasonal and Weekday/Weekend", "Average Day", 2030)

        | season | day_type | year | 1      | 2      | 3      | ... | 23     | 24     |
        |--------|----------|------|--------|--------|--------|-----|--------|--------|
        | Winter | Weekday  | 2025 | 3400.5 | 3350.2 | 3320.8 | ... | 3380.4 | 3420.1 |
        | Winter | Weekend  | 2025 | 3000.3 | 2950.8 | 2920.5 | ... | 2980.2 | 3020.6 |
        | Spring | Weekday  | 2025 | 2900.7 | 2850.3 | 2820.9 | ... | 2880.5 | 2920.8 |
        | Spring | Weekend  | 2025 | 2600.2 | 2550.5 | 2520.1 | ... | 2580.7 | 2620.4 |
        """
        pass
