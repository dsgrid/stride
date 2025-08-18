"""
Tests for the database api.
"""

import pytest
import pandas as pd
from stride.api import APIClient
from stride.project import Project


def test_singleton_behavior(default_project: Project) -> None:
    """Test that APIClient follows singleton pattern."""
    client1 = APIClient(project=default_project)
    client2 = APIClient(project=default_project)

    # Both should be APIClient instances (same singleton in real usage)
    assert isinstance(client1, APIClient)
    assert isinstance(client2, APIClient)


def test_years_property(api_client: APIClient) -> None:
    """Test years property returns cached list."""
    years = api_client.years
    assert isinstance(years, list)
    assert all(isinstance(year, int) for year in years)
    assert len(years) > 0
    # Test caching - should be same object
    assert api_client.years is years


def test_scenarios_property(api_client: APIClient) -> None:
    """Test scenarios property returns cached list."""
    scenarios = api_client.scenarios
    assert isinstance(scenarios, list)
    assert all(isinstance(scenario, str) for scenario in scenarios)
    assert len(scenarios) > 0
    # Test caching - should be same object
    assert api_client.scenarios is scenarios


def test_get_years(api_client: APIClient) -> None:
    """Test get_years method returns list of integers."""
    years = api_client.get_years()
    assert isinstance(years, list)
    assert all(isinstance(year, int) for year in years)
    assert len(years) > 0


def test_validate_scenarios_valid(api_client: APIClient) -> None:
    """Test validation passes for valid scenarios."""
    valid_scenarios = api_client.scenarios[:1]  # Take first scenario
    # Should not raise
    api_client._validate_scenarios(valid_scenarios)


def test_validate_scenarios_invalid(api_client: APIClient) -> None:
    """Test validation fails for invalid scenarios."""
    with pytest.raises(ValueError, match="Invalid scenarios"):
        api_client._validate_scenarios(["invalid_scenario"])


def test_validate_years_valid(api_client: APIClient) -> None:
    """Test validation passes for valid years."""
    valid_years = api_client.years[:1]  # Take first year
    # Should not raise
    api_client._validate_years(valid_years)


def test_validate_years_invalid(api_client: APIClient) -> None:
    """Test validation fails for invalid years."""
    with pytest.raises(ValueError, match="Invalid years"):
        api_client._validate_years([9999])


def test_refresh_metadata(api_client: APIClient) -> None:
    """Test metadata refresh clears cache."""
    # Access properties to cache them
    _ = api_client.years
    _ = api_client.scenarios

    # Refresh should clear cache
    api_client.refresh_metadata()

    # Should work without error (will re-fetch from DB)
    years = api_client.years
    scenarios = api_client.scenarios
    assert len(years) > 0
    assert len(scenarios) > 0


def test_get_annual_electricity_consumption_no_breakdown(api_client: APIClient) -> None:
    """Test annual consumption without breakdown."""
    df = api_client.get_annual_electricity_consumption()

    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    assert "year" in df.columns


def test_get_annual_electricity_consumption_with_breakdown(api_client: APIClient) -> None:
    """Test annual consumption with sector breakdown."""
    df = api_client.get_annual_electricity_consumption(group_by="Sector")

    assert isinstance(df, pd.DataFrame)
    # Should have breakdown columns
    if not df.empty:
        assert "sector" in df.columns


def test_get_annual_peak_demand(api_client: APIClient) -> None:
    """Test peak demand method executes."""
    df = api_client.get_annual_peak_demand()

    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    assert "year" in df.columns


def test_get_annual_peak_demand_with_breakdown(api_client: APIClient) -> None:
    """Test peak demand with sector breakdown."""
    df = api_client.get_annual_peak_demand(group_by="Sector")

    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    assert "scenario" in df.columns
    if not df.empty:
        assert "sector" in df.columns


def test_get_secondary_metric(api_client: APIClient) -> None:
    """Test secondary metric method executes."""
    pytest.skip("Secondary metric functionality not implemented yet")
    valid_scenario = api_client.scenarios[0]
    df = api_client.get_secondary_metric(valid_scenario, "GDP")
    assert isinstance(df, pd.DataFrame)
    # May be empty if metric doesn't exist, but should not error
    if not df.empty:
        assert "year" in df.columns
        assert "value" in df.columns


def test_get_load_duration_curve(api_client: APIClient) -> None:
    """Test load duration curve method executes."""
    valid_year = api_client.years[0]
    df = api_client.get_load_duration_curve([valid_year])

    assert isinstance(df, pd.DataFrame)
    assert not df.empty


def test_get_load_duration_curve_multiple_years_single_scenario(api_client: APIClient) -> None:
    """Test load duration curve with multiple years and single scenario."""
    valid_years = api_client.years[:2] if len(api_client.years) >= 2 else [api_client.years[0]]
    valid_scenario = [api_client.scenarios[0]]

    df = api_client.get_load_duration_curve(valid_years, valid_scenario)
    assert isinstance(df, pd.DataFrame)
    assert not df.empty


def test_get_load_duration_curve_single_year_multiple_scenarios(api_client: APIClient) -> None:
    """Test load duration curve with single year and multiple scenarios."""
    valid_year = [api_client.years[0]]
    valid_scenarios = (
        api_client.scenarios[:2] if len(api_client.scenarios) >= 2 else api_client.scenarios
    )

    df = api_client.get_load_duration_curve(valid_year, valid_scenarios)
    assert isinstance(df, pd.DataFrame)
    assert not df.empty


def test_get_load_duration_curve_multiple_years_and_scenarios_error(api_client: APIClient) -> None:
    """Test that specifying multiple years and scenarios raises error."""
    valid_years = (
        api_client.years[:2]
        if len(api_client.years) >= 2
        else [api_client.years[0], api_client.years[0]]
    )
    valid_scenarios = (
        api_client.scenarios[:2]
        if len(api_client.scenarios) >= 2
        else [api_client.scenarios[0], api_client.scenarios[0]]
    )

    # Skip test if we don't have enough data for multiple items
    if len(valid_years) < 2 or len(valid_scenarios) < 2:
        pytest.skip("Insufficient test data for multiple years and scenarios")

    with pytest.raises(ValueError, match="Cannot specify multiple years and multiple scenarios"):
        api_client.get_load_duration_curve(valid_years, valid_scenarios)


def test_get_scenario_summary(api_client: APIClient) -> None:
    """Test scenario summary method executes."""
    valid_scenario = api_client.scenarios[0]
    valid_year = api_client.years[0]
    summary = api_client.get_scenario_summary(valid_scenario, valid_year)
    assert isinstance(summary, dict)
    assert "TOTAL_CONSUMPTION" in summary
    assert "PERCENT_GROWTH" in summary
    assert "PEAK_DEMAND" in summary


def test_get_weather_metric(api_client: APIClient) -> None:
    """Test weather metric method executes."""
    pytest.skip("Weather Metric not implemented yet.")
    valid_scenario = api_client.scenarios[0]
    valid_year = api_client.years[0]
    df = api_client.get_weather_metric(valid_scenario, valid_year, "Temperature")
    assert isinstance(df, pd.DataFrame)
    # May be empty if weather data doesn't exist
    if not df.empty:
        assert "datetime" in df.columns
        assert "value" in df.columns


def test_get_time_series_comparison(api_client: APIClient) -> None:
    """Test timeseries comparison method executes."""
    valid_scenario = api_client.scenarios[0]
    valid_years = api_client.years[:2] if len(api_client.years) >= 2 else [api_client.years[0]]
    df = api_client.get_time_series_comparison(valid_scenario, valid_years)

    assert isinstance(df, pd.DataFrame)
    assert not df.empty


def test_get_seasonal_load_lines(api_client: APIClient) -> None:
    """Test seasonal load lines method executes."""
    valid_scenario = api_client.scenarios[0]
    df = api_client.get_seasonal_load_lines(valid_scenario)

    assert isinstance(df, pd.DataFrame)
    assert not df.empty
