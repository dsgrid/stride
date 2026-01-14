"""
Tests for the UI callbacks.
"""

import pytest
import plotly.graph_objects as go
from typing import Literal, Any

from stride.ui.plotting import StridePlots
from stride.ui.color_manager import ColorManager
from stride.api import APIClient
from stride.api.utils import (
    ConsumptionBreakdown,
    SecondaryMetric,
    TimeGroup,
    TimeGroupAgg,
    ResampleOptions,
    WeatherVar,
    ChartType,
    literal_to_list,
)

from stride.ui.home.callbacks import (
    update_home_scenario_comparison,
    update_home_sector_breakdown,
    update_home_load_duration,
    update_home_scenario_timeseries,
    save_home_state,
)
from stride.ui.scenario.callbacks import (
    update_summary_stats,
    update_consumption_plot,
    update_peak_plot,
    update_timeseries_plot,
    update_yearly_plot,
    update_seasonal_lines_plot,
    update_seasonal_area_plot,
    update_load_duration_plot,
)


@pytest.fixture
def plotter() -> StridePlots:
    """Create a real plotter instance."""
    color_manager = ColorManager()
    return StridePlots(color_manager)


def assert_valid_figure(result: go.Figure | dict[str, Any]) -> None:
    """Helper function to assert that result is a valid plotly figure."""
    assert isinstance(result, go.Figure)
    assert "data" in result
    assert "layout" in result
    # Should not be an error message
    if "title" in result["layout"]:
        assert "Error" not in result["layout"]["title"]
        assert "Select" not in result["layout"]["title"]  # Not a "Select data" message


# Home Callbacks Tests
def test_save_home_state() -> None:
    """Test home state saving functionality."""
    test_values = [
        "None",  # consumption-breakdown
        "GDP",  # secondary-metric
        ["baseline", "high_growth"],  # scenarios-checklist
        "Sector",  # peak-breakdown
        "GDP",  # peak-secondary-metric
        ["baseline"],  # scenarios-2-checklist
        2030,  # year-dropdown
        ["high_growth"],  # scenarios-3-checklist
        "Line",  # timeseries-chart-type
        "End Use",  # timeseries-breakdown
        "GDP Per Capita",  # timeseries-secondary-metric
        ["baseline", "high_growth"],  # scenarios-4-checklist
    ]

    result = save_home_state(*test_values)

    assert isinstance(result, dict)
    assert len(result) == 12
    assert result["home-consumption-breakdown"] == "None"
    assert result["home-scenarios-checklist"] == ["baseline", "high_growth"]
    assert result["home-year-dropdown"] == 2030


def test_update_home_scenario_comparison_no_scenarios(
    api_client: APIClient, plotter: StridePlots
) -> None:
    """Test scenario comparison with no scenarios selected."""
    # Note: api_client is session-scoped, do not mutate
    result = update_home_scenario_comparison(api_client, plotter, [], "None", "GDP")

    assert isinstance(result, dict)
    assert result["layout"]["title"] == "Select scenarios to view data"


@pytest.mark.parametrize("breakdown", literal_to_list(ConsumptionBreakdown, include_none_str=True))
@pytest.mark.parametrize(
    "secondary_metric", literal_to_list(SecondaryMetric, include_none_str=True)
)
def test_update_home_scenario_comparison(
    api_client: APIClient,
    plotter: StridePlots,
    breakdown: ConsumptionBreakdown | Literal["None"],
    secondary_metric: SecondaryMetric | Literal["None"],
) -> None:
    """Test scenario comparison with different breakdown and secondary metric combinations."""
    # Use actual scenarios from the API client
    available_scenarios = (
        api_client.scenarios[:2] if len(api_client.scenarios) >= 2 else api_client.scenarios
    )

    result = update_home_scenario_comparison(
        api_client, plotter, available_scenarios, breakdown, secondary_metric
    )

    # Verify we get a valid plotly figure
    assert_valid_figure(result)


@pytest.mark.parametrize("breakdown", literal_to_list(ConsumptionBreakdown, include_none_str=True))
@pytest.mark.parametrize(
    "secondary_metric", literal_to_list(SecondaryMetric, include_none_str=True)
)
def test_update_home_sector_breakdown(
    api_client: APIClient,
    plotter: StridePlots,
    breakdown: ConsumptionBreakdown | Literal["None"],
    secondary_metric: SecondaryMetric | Literal["None"],
) -> None:
    """Test home sector breakdown (peak demand) with different combinations."""
    available_scenarios = api_client.scenarios[:1] if api_client.scenarios else []

    result = update_home_sector_breakdown(
        api_client, plotter, available_scenarios, breakdown, secondary_metric
    )

    assert_valid_figure(result)


def test_update_home_load_duration(api_client: APIClient, plotter: StridePlots) -> None:
    """Test home load duration callback."""
    available_scenarios = (
        api_client.scenarios[:2] if len(api_client.scenarios) >= 2 else api_client.scenarios
    )
    available_year = api_client.years[0]

    result = update_home_load_duration(api_client, plotter, available_scenarios, available_year)

    assert_valid_figure(result)


def test_update_home_load_duration_no_data(api_client: APIClient, plotter: StridePlots) -> None:
    """Test home load duration with no scenarios or year."""
    selected_year = api_client.years[0]

    result = update_home_load_duration(api_client, plotter, ["invalid"], selected_year)

    assert result == {}


@pytest.mark.parametrize("chart_type", literal_to_list(ChartType))
@pytest.mark.parametrize("breakdown", literal_to_list(ConsumptionBreakdown, include_none_str=True))
@pytest.mark.parametrize(
    "secondary_metric", literal_to_list(SecondaryMetric, include_none_str=True)
)
def test_update_home_scenario_timeseries(
    api_client: APIClient,
    plotter: StridePlots,
    chart_type: ChartType,
    breakdown: ConsumptionBreakdown | Literal["None"],
    secondary_metric: SecondaryMetric | Literal["None"],
) -> None:
    """Test home scenario timeseries with different combinations."""
    available_scenarios = api_client.scenarios[:1] if api_client.scenarios else []

    result = update_home_scenario_timeseries(
        api_client, plotter, available_scenarios, chart_type, breakdown, secondary_metric
    )

    assert_valid_figure(result)


def test_update_home_scenario_timeseries_error_handling(
    api_client: APIClient, plotter: StridePlots
) -> None:
    """Test error handling in home scenario timeseries."""
    # Test with invalid scenario to trigger error handling
    result = update_home_scenario_timeseries(
        api_client, plotter, ["invalid_scenario"], "Line", "None", "GDP"
    )

    assert isinstance(result, dict)
    assert "Error" in result["layout"]["title"]


# Scenario Callbacks Tests
def test_update_summary_stats_valid_inputs(api_client: APIClient) -> None:
    """Test summary stats with valid inputs."""
    # Note: api_client is session-scoped, do not mutate
    available_scenario = api_client.scenarios[0]
    available_year = api_client.years[-1]  # Use last year for growth calculation

    total, consumption_cagr, peak, peak_cagr = update_summary_stats(
        api_client, available_scenario, available_year
    )

    # Should return formatted strings
    assert isinstance(total, str)
    assert isinstance(consumption_cagr, str)
    assert isinstance(peak, str)
    assert isinstance(peak_cagr, str)

    # Should not be error values
    assert total != "Error"
    assert consumption_cagr != "Error"
    assert peak != "Error"
    assert peak_cagr != "Error"


def test_update_summary_stats_first_year(api_client: APIClient) -> None:
    """Test summary stats for first year (no growth calculation)."""
    available_scenario = api_client.scenarios[0]
    first_year = api_client.years[0]

    total, consumption_cagr, peak, peak_cagr = update_summary_stats(
        api_client, available_scenario, first_year
    )

    assert isinstance(total, str)
    assert consumption_cagr == "N/A"  # First year has no previous year
    assert isinstance(peak, str)
    assert peak_cagr == "N/A"  # First year has no previous year


def test_update_summary_stats_invalid_inputs(api_client: APIClient) -> None:
    """Test summary stats with invalid inputs."""
    # Invalid scenario
    total, consumption_cagr, peak, peak_cagr = update_summary_stats(api_client, "invalid", 2030)
    assert total == "---"
    assert consumption_cagr == "---"
    assert peak == "---"
    assert peak_cagr == "---"


@pytest.mark.parametrize("breakdown", literal_to_list(ConsumptionBreakdown, include_none_str=True))
@pytest.mark.parametrize(
    "secondary_metric", literal_to_list(SecondaryMetric, include_none_str=True)
)
def test_update_consumption_plot(
    api_client: APIClient,
    plotter: StridePlots,
    breakdown: ConsumptionBreakdown | Literal["None"],
    secondary_metric: SecondaryMetric | Literal["None"],
) -> None:
    """Test consumption plot with different breakdown and secondary metric combinations."""
    available_scenario = api_client.scenarios[0]

    result = update_consumption_plot(
        api_client, plotter, available_scenario, breakdown, secondary_metric
    )

    assert_valid_figure(result)


@pytest.mark.parametrize("breakdown", literal_to_list(ConsumptionBreakdown, include_none_str=True))
@pytest.mark.parametrize(
    "secondary_metric", literal_to_list(SecondaryMetric, include_none_str=True)
)
def test_update_peak_plot(
    api_client: APIClient,
    plotter: StridePlots,
    breakdown: ConsumptionBreakdown | Literal["None"],
    secondary_metric: SecondaryMetric | Literal["None"],
) -> None:
    """Test peak demand plot with different breakdown and secondary metric combinations."""
    available_scenario = api_client.scenarios[0]

    result = update_peak_plot(api_client, plotter, available_scenario, breakdown, secondary_metric)

    assert_valid_figure(result)


@pytest.mark.parametrize("breakdown", literal_to_list(ConsumptionBreakdown, include_none_str=True))
@pytest.mark.parametrize("resample", literal_to_list(ResampleOptions))
@pytest.mark.parametrize("weather_var", literal_to_list(WeatherVar, include_none_str=True))
def test_update_timeseries_plot(
    api_client: APIClient,
    plotter: StridePlots,
    breakdown: ConsumptionBreakdown | Literal["None"],
    resample: ResampleOptions,
    weather_var: WeatherVar | Literal["None"],
) -> None:
    """Test timeseries plot with different parameter combinations."""
    # Convert "None" to None for weather_var
    weather_var_value = None if weather_var == "None" else weather_var

    # Skip if weather data is specified (not implemented yet)
    if weather_var_value is not None:
        pytest.skip("Weather data functionality not implemented yet")

    available_scenario = api_client.scenarios[0]
    available_years = api_client.years[:2] if len(api_client.years) >= 2 else api_client.years

    result = update_timeseries_plot(
        api_client,
        plotter,
        available_scenario,
        breakdown,
        resample,
        weather_var_value,
        available_years,
    )

    assert_valid_figure(result)


def test_update_timeseries_plot_no_years(api_client: APIClient, plotter: StridePlots) -> None:
    """Test timeseries plot with no years selected."""
    available_scenario = api_client.scenarios[0]

    result = update_timeseries_plot(
        api_client, plotter, available_scenario, "None", "Daily Mean", None, []
    )

    assert isinstance(result, dict)
    assert result["layout"]["title"] == "Select years to view data"


@pytest.mark.parametrize("breakdown", literal_to_list(ConsumptionBreakdown, include_none_str=True))
@pytest.mark.parametrize("resample", literal_to_list(ResampleOptions))
@pytest.mark.parametrize("weather_var", literal_to_list(WeatherVar, include_none_str=True))
def test_update_yearly_plot(
    api_client: APIClient,
    plotter: StridePlots,
    breakdown: ConsumptionBreakdown | Literal["None"],
    resample: ResampleOptions,
    weather_var: WeatherVar | Literal["None"],
) -> None:
    """Test yearly area plot with different parameter combinations."""
    # Convert "None" to None for weather_var
    weather_var_value = None if weather_var == "None" else weather_var

    # Skip if weather data is specified (not implemented yet)
    if weather_var_value is not None:
        pytest.skip("Weather data functionality not implemented yet")

    available_scenario = api_client.scenarios[0]
    available_year = api_client.years[0]

    result = update_yearly_plot(
        api_client,
        plotter,
        available_scenario,
        breakdown,
        resample,
        weather_var_value,
        [available_year],
    )
    assert_valid_figure(result)


@pytest.mark.parametrize("timegroup", literal_to_list(TimeGroup))
@pytest.mark.parametrize("agg", literal_to_list(TimeGroupAgg))
@pytest.mark.parametrize("weather_var", literal_to_list(WeatherVar, include_none_str=True))
def test_update_seasonal_lines_plot(
    api_client: APIClient,
    plotter: StridePlots,
    timegroup: TimeGroup,
    agg: TimeGroupAgg,
    weather_var: WeatherVar | Literal["None"],
) -> None:
    """Test seasonal load lines plot with different parameter combinations."""
    # Convert "None" to None for weather_var
    weather_var_value = None if weather_var == "None" else weather_var

    # Skip if weather data is specified (not implemented yet)
    if weather_var_value is not None:
        pytest.skip("Weather data functionality not implemented yet")

    available_scenario = api_client.scenarios[0]

    result = update_seasonal_lines_plot(
        api_client, plotter, available_scenario, timegroup, agg, weather_var_value
    )

    assert_valid_figure(result)


@pytest.mark.parametrize("breakdown", literal_to_list(ConsumptionBreakdown, include_none_str=True))
@pytest.mark.parametrize("timegroup", literal_to_list(TimeGroup))
@pytest.mark.parametrize("agg", literal_to_list(TimeGroupAgg))
@pytest.mark.parametrize("weather_var", literal_to_list(WeatherVar, include_none_str=True))
def test_update_seasonal_area_plot(
    api_client: APIClient,
    plotter: StridePlots,
    breakdown: ConsumptionBreakdown | Literal["None"],
    timegroup: TimeGroup,
    agg: TimeGroupAgg,
    weather_var: WeatherVar | Literal["None"],
) -> None:
    """Test seasonal load area plot with different parameter combinations."""
    # Convert "None" to None for weather_var
    weather_var_value = None if weather_var == "None" else weather_var

    # Skip if weather data is specified (not implemented yet)
    if weather_var_value is not None:
        pytest.skip("Weather data functionality not implemented yet")

    available_scenario = api_client.scenarios[0]
    available_year = api_client.years[0]

    result = update_seasonal_area_plot(
        api_client,
        plotter,
        available_scenario,
        breakdown,
        available_year,
        timegroup,
        agg,
        weather_var_value,
    )

    assert_valid_figure(result)


def test_update_load_duration_plot(api_client: APIClient, plotter: StridePlots) -> None:
    """Test load duration curve plot callback."""
    available_scenario = api_client.scenarios[0]
    available_years = api_client.years[:2] if len(api_client.years) >= 2 else api_client.years

    result = update_load_duration_plot(api_client, plotter, available_scenario, available_years)

    assert_valid_figure(result)


def test_update_load_duration_plot_no_years(api_client: APIClient, plotter: StridePlots) -> None:
    """Test load duration plot with no years selected."""
    available_scenario = api_client.scenarios[0]

    result = update_load_duration_plot(api_client, plotter, available_scenario, [])

    assert isinstance(result, dict)
    assert result["layout"]["title"] == "Select years to view data"


# Error Handling Tests
def test_home_callback_api_error(api_client: APIClient, plotter: StridePlots) -> None:
    """Test home callback handles API errors gracefully."""
    # Note: api_client is session-scoped, do not mutate
    # Use invalid scenario to trigger error
    result = update_home_scenario_comparison(
        api_client, plotter, ["invalid_scenario"], "None", "GDP"
    )

    assert isinstance(result, dict)
    assert "Error" in result["layout"]["title"]


def test_scenario_callback_api_error(api_client: APIClient, plotter: StridePlots) -> None:
    """Test scenario callback handles API errors gracefully."""
    # Use invalid scenario to trigger error
    result = update_consumption_plot(api_client, plotter, "invalid_scenario", "None", "GDP")

    assert isinstance(result, dict)
    assert "Error" in result["layout"]["title"]


def test_summary_stats_exception(api_client: APIClient) -> None:
    """Test summary stats handles exceptions."""
    # Use invalid scenario to trigger error
    total, consumption_cagr, peak, peak_cagr = update_summary_stats(
        api_client, "invalid_scenario", 2030
    )

    assert total == "---"
    assert consumption_cagr == "---"
    assert peak == "---"
    assert peak_cagr == "---"
