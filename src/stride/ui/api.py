"""
API functions that run a SQL query against the local duckdb instance and
return a dataframe for direct use with plotly/Dash

Lingering Questions/Comments:
1. We need some way of determining the valid model years. Preferably a fast lookup of the project config.
2. For secondary metrics, how do we handle different versions of table overrides (e.g. Two versions of GDP)
3. What is "Absolute Value" in the Scenario Summary Stats? (Assuming total consumption (TWh))
4. In the timeseries charts, It seems like Daily or Weekly mean should be in separate dropdown category.
5. For Comparing two timeseries, we need to handle displaying the secondary axis weather variable for both model years

"""
import pandas as pd
from typing import Optional, Any, Union
from enum import Enum


class ConsumptionBreakdown(Enum):
    TOTAL = "Total"
    SECTOR = "Sector"
    END_USE = "End Use"

class Unit(Enum):
    KW = "kW"
    MW = "MW"
    TW = "TW"
    TWH = "TWh"

class SecondaryMetric(Enum):
    EV_ADOPTION_PERC= "Percent EV Adoption"
    POPULATION = "Population"
    GDP = "GDP"
    GDP_PER_CAP = "GDP Per Capita"
    HDI = "Human Development Index"
    STOCK = "Stock"


class WeatherVar(Enum):
    T="Temperature"
    H="Humidity"

class Sectors(Enum):
    T="Transportation"
    I="Industrial"
    C="Commercial"
    R="Residential"
    O="Other"

class ChartType(Enum):
    AREA="Area"
    LINE="Line"


class ResampleOptions(Enum):
    NONE=None # No Resampling
    DAILY_MEAN='Daily Mean'
    Weekly_MEAN='Weekly Mean'

class TimeGroup(Enum):
    SEASONAL="Seasonal"
    WEEKDAY_WEEKEND="Weekday/Weekend"
    SEASONAL_WEEKDAY_WEEKEND="Seasonal and Weekday/Weekend"

class TimeGroupAgg(Enum):
    AVG="Average Day"
    PEAK="Peak Day"
    MIN="Minimum Day"
    MED="MEDIAN DAY"

# UTILITY FUNCTIONS

def valid_model_years()->list[int]:

    """
    Returns
    -------
    A list of valid model years. Used for validating inputs into api query functions.
    """

def list_project_scenarios()->list[str]:
    """
    Returns
    -------
    A list of valid scenarios. Used for validating inputs into api query functions.

    """
    pass

# COMBINED CHART SECTION
# Do we want the ability to filter out scenarios at the Query Level rather than just the UI display?
def annual_electricity_consumption(
        years: Optional[list[int]] = None, # Valid model years for the project. Currently no option to filter years shown in wireframe.
        by: Optional[ConsumptionBreakdown]=ConsumptionBreakdown.TOTAL, # by Sector or by End Use
        scenarios: Optional[list[Any]]=None, # Optionally Exclude Scenarios.
    )->pd.DataFrame:

    """Queries the Total Annual Consumption for each scenario.
    Optionally, Break down the consumption by Sector or End Use.

    Parameters
    ----------

    years: int = Valid weather years for the opened project
    by: optionally breakdown by Sector and end Use
    scenarios: optional list of scenarios to filter by

    Returns
    -------
    A column for each year.
    A row for each row group e.g. (Scenario{i}, Total), (Scenario{i}, sector), or (Scenario{i}, End Use)
    """

    pass


def annual_peak_demand(
        years: Optional[list[int]]=None,
        by: Optional[ConsumptionBreakdown]=ConsumptionBreakdown.TOTAL,
        scenarios: Optional[list[Any]]=None
    )->pd.DataFrame:
    """Queries the Peak Annual Consumption for each scenario.
    Optionally, Break down the consumption by Sector or End Use.

    !! For Peak Consumption by Sector Or End Use, the timestamp of the Total Peak is used. Then the
    timestamps are queried to get the end use or Sector demand for that particular timestamp. !!

    Parameters
    ----------

    years: int = Valid weather years for the opened project
    by: optionally breakdown by Sector and end Use
    scenarios: optional list of scenarios to filter by

    Returns
    -------
    A column for each year.
    A row for each row group e.g. (Scenario{i}, Total), (Scenario{i}, sector), or (Scenario{i}, End Use)
    """


def secondary_metric(metric: SecondaryMetric, years: Optional[list[int]]=None)->pd.DataFrame:
    """
    Queries the database for the secondary metric to overlay against a particular plot on the secondary axis

    !!!Must be able to handle multiple overrides of a particular metric to differentiate between scenarios!!!

    Paramaters
    ----------

    metric: The secondary metric to query.
    years: A list of valid model years to filter by. Uses all model years if None specified.

    Returns
    -------
    A dataframe with a row for each valid model year and column for each chosen scenario or All Scenarios if none.


    """


def load_duration_curve(
        year: int,
        unit: str='kW', # Remove if not needed
        scenarios: Optional[list[str]]=None, # in case we want to filter scenarios from the UI from a drop-down rather than plotly filters.
                        )->pd.DataFrame:


    """Gets the load duration curve for each scenario
    Parameters
    ----------
    year: A valid year for the given project.

    Returns
    -------

    A dataframe with a column of total demand for each scenario. Each column
    is sorted independently from largest value to smallest..

    Index is a row-number index.
    """

    pass


# COMPARISON CHARTS

"""These seem to utilize the same annual_electricity_consumption data, but instead scenarios are faceted charts rather
than grouped bar charts. We should be able to use the same data"""


# Scenario Charts
"""Charts for a given Scenario. (no comparison to other scenarios)"""

# KPIS

def get_scenario_summary(year: int)->dict[str,float]:
    """

    Parameters
    ----------

    Returns
    -------

    Returns a dictionary of KPI metrics {TOTAL_CONSUMPTION: val, PERC_GROWTH: val, PEAK_DMD: Val, ...}
    """
    pass


"""
Total Electricity Consumption (all or by sector/end use) (Single Scenario).

Uses the same annual_electricity_consumption API as above but uses a specific scenario
"""

"""
Total Peak Demand (all or by sector/end use) (single Scenario)

Uses the same annual_peak_demand() API but uses only a single Scenario value.
"""


def weather_metric(model_year: int,
    wvar: WeatherMetric,
    scenario:str,
    resample: Optional[ResampleOptions]=None
    timegroup: Optional[TimeGroup]
    )->pd.Series:
    """
    Gets the weather timeseries data to use as a secondary axis. Optionally Resample to Daily or weekly mean

    Parameters
    ----------
    model_year: The valid model year to choose for the weather metric (temperature or humidity)
    wvar: The weather variable to choose,
    scenario: The scenario specific weather source data.

    Returns
    ------
    A pandas series of Temperature or Humidity, optionally resampled to daily or weekly.
    """"
    pass



def timeseries_comparison(
    consumption_breakdown: ConsumptionBreakdown,
    model_years: Union[int, list[int]],
    resample: Optional[ResampleOptions]=ResampleOptions.DAILY_MEAN
    )->pd.Dataframe:

    """
    User selects no more than 2 model years. Returns a generator.

    Parameters
    ----------
    consumption_breakdown: The load broken down by sector or end use.
    model_years: 1 or 2 model years to view on the same chart.


    Yields
    -------
    DataFrames of Electricity consumption (total, by sector, or by End Use) and avereaged Daily or Weekly.

    """
    pass


"""YEARLY TIMESERIES. Uses the same as above, but limits it to one single year."""

def seasonal_load_lines(
    scenario: str,
    by: TimeGroup,
    agg: TimeGroupAgg,
    model_years: Optional[Union[int, list[int]]],
    )->pd.Dataframe:

    """

    Parameters
    ----------
    scenario: A valid scenario within the project.
    by: Seasonal, Weekday/Weekend, or Both.
    agg: How to aggregate each hour of the day.
    model_years: A single or list of valid model years.

    """
    pass

def seasonal_load_area(
    scenario: str,
    by: ConsumptionBreakdown,
    agg: TimeGroupAgg,
    model_year: int,
)
    """

    Parameters
    ----------
    scenario: A valid scenario within the project
    by: Total, Sector or End Use
    agg: How to aggregate the hours of the day (mean, max, min median)
    model_year: A single valid model year.

    """
    pass


"""LOAD DURATION CURVE - Single Scenario - Multiple Years"""

