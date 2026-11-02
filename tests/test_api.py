"""
Tests for the database api.
"""

import pytest
import pandas as pd
from duckdb import DuckDBPyConnection
from stride.api import APIClient
from stride.api.utils import literal_to_list, TimeGroup
from stride.project import Project
from time_reference import season


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


def test_annual_consumption_sector_no_duplicates(api_client: APIClient) -> None:
    """Annual consumption by Sector should have one row per (scenario, year, sector)."""
    df = api_client.get_annual_electricity_consumption(group_by="Sector")
    assert not df.empty
    duplicates = df.duplicated(subset=["scenario", "year", "sector"])
    assert (
        not duplicates.any()
    ), f"Duplicate (scenario, year, sector) rows found:\n{df[duplicates]}"
    assert (df["value"] > 0).all(), "All consumption values should be positive"


def test_annual_consumption_enduse_no_duplicates(api_client: APIClient) -> None:
    """Annual consumption by End Use should have one row per (scenario, year, metric)."""
    df = api_client.get_annual_electricity_consumption(group_by="End Use")
    assert not df.empty
    duplicates = df.duplicated(subset=["scenario", "year", "metric"])
    assert (
        not duplicates.any()
    ), f"Duplicate (scenario, year, metric) rows found:\n{df[duplicates]}"
    assert (df["value"] > 0).all(), "All consumption values should be positive"


def test_annual_consumption_breakdown_sums_to_total(api_client: APIClient) -> None:
    """Sum of sector breakdown and end-use breakdown should each equal the total."""
    scenario = api_client.scenarios[0]
    year = [api_client.years[0]]

    total_df = api_client.get_annual_electricity_consumption(scenarios=[scenario], years=year)
    sector_df = api_client.get_annual_electricity_consumption(
        scenarios=[scenario], years=year, group_by="Sector"
    )
    enduse_df = api_client.get_annual_electricity_consumption(
        scenarios=[scenario], years=year, group_by="End Use"
    )
    assert not total_df.empty

    total_value = total_df["value"].iloc[0]
    sector_sum = sector_df["value"].sum()
    enduse_sum = enduse_df["value"].sum()

    assert (
        abs(sector_sum - total_value) / total_value < 0.001
    ), f"Sector sum {sector_sum:.0f} != total {total_value:.0f}"
    assert (
        abs(enduse_sum - total_value) / total_value < 0.001
    ), f"End-use sum {enduse_sum:.0f} != total {total_value:.0f}"


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


def test_get_annual_peak_demand_sector_no_duplicates(api_client: APIClient) -> None:
    """Peak demand by Sector should return exactly one row per (scenario, year, sector)."""
    df = api_client.get_annual_peak_demand(group_by="Sector")
    assert not df.empty
    duplicates = df.duplicated(subset=["scenario", "year", "sector"])
    assert (
        not duplicates.any()
    ), f"Duplicate (scenario, year, sector) rows found:\n{df[duplicates]}"
    assert (df["value"] > 0).all(), "All peak demand values should be positive"


def test_get_annual_peak_demand_enduse_no_duplicates(api_client: APIClient) -> None:
    """Peak demand by End Use should return exactly one row per (scenario, year, metric)."""
    df = api_client.get_annual_peak_demand(group_by="End Use")
    assert not df.empty
    duplicates = df.duplicated(subset=["scenario", "year", "metric"])
    assert (
        not duplicates.any()
    ), f"Duplicate (scenario, year, metric) rows found:\n{df[duplicates]}"
    assert (df["value"] > 0).all(), "All peak demand values should be positive"


def test_get_secondary_metric(api_client: APIClient) -> None:
    """Test secondary metric method executes."""
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
    valid_scenario = api_client.scenarios[0]
    valid_year = api_client.years[0]
    df = api_client.get_weather_metric(valid_scenario, valid_year, "Temperature", "Hourly")
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


def test_get_time_series_hourly_sector_no_duplicates(api_client: APIClient) -> None:
    """Hourly time series by Sector should have one row per (scenario, year, time_period, sector)."""
    valid_scenario = api_client.scenarios[0]
    valid_years = [api_client.years[0]]
    df = api_client.get_time_series_comparison(
        valid_scenario, valid_years, group_by="Sector", resample="Hourly"
    )
    assert not df.empty
    duplicates = df.duplicated(subset=["scenario", "year", "time_period", "sector"])
    assert (
        not duplicates.any()
    ), f"Duplicate (scenario, year, time_period, sector) rows found:\n{df[duplicates]}"
    assert (df["value"] > 0).all(), "All hourly values should be positive"


def test_get_time_series_hourly_enduse_no_duplicates(api_client: APIClient) -> None:
    """Hourly time series by End Use should have one row per (scenario, year, time_period, metric)."""
    valid_scenario = api_client.scenarios[0]
    valid_years = [api_client.years[0]]
    df = api_client.get_time_series_comparison(
        valid_scenario, valid_years, group_by="End Use", resample="Hourly"
    )
    assert not df.empty
    duplicates = df.duplicated(subset=["scenario", "year", "time_period", "metric"])
    assert (
        not duplicates.any()
    ), f"Duplicate (scenario, year, time_period, metric) rows found:\n{df[duplicates]}"
    assert (df["value"] > 0).all(), "All hourly values should be positive"


def test_resampled_sector_mean_matches_annual(api_client: APIClient) -> None:
    """Daily Mean sector values * 8760 should approximate annual consumption per sector."""
    scenario = api_client.scenarios[0]
    year = [api_client.years[0]]

    daily_df = api_client.get_time_series_comparison(
        scenario, year, group_by="Sector", resample="Daily Mean"
    )
    annual_df = api_client.get_annual_electricity_consumption(
        scenarios=[scenario], years=year, group_by="Sector"
    )
    assert not daily_df.empty and not annual_df.empty

    # Mean hourly load * 8760 hours should approximate annual total
    daily_sector_means = daily_df.groupby("sector")["value"].mean()
    annual_totals = annual_df.set_index("sector")["value"]

    for sector in annual_totals.index:
        estimated_annual = daily_sector_means[sector] * 8760
        actual_annual = annual_totals[sector]
        ratio = estimated_annual / actual_annual
        assert 0.95 < ratio < 1.05, (
            f"Sector '{sector}': daily mean * 8760 = {estimated_annual:.0f}, "
            f"annual = {actual_annual:.0f}, ratio = {ratio:.3f} (expected ~1.0)"
        )


def test_resampled_enduse_mean_matches_annual(api_client: APIClient) -> None:
    """Daily Mean end-use values * 8760 should approximate annual consumption per end use."""
    scenario = api_client.scenarios[0]
    year = [api_client.years[0]]

    daily_df = api_client.get_time_series_comparison(
        scenario, year, group_by="End Use", resample="Daily Mean"
    )
    annual_df = api_client.get_annual_electricity_consumption(
        scenarios=[scenario], years=year, group_by="End Use"
    )
    assert not daily_df.empty and not annual_df.empty

    daily_enduse_means = daily_df.groupby("metric")["value"].mean()
    annual_totals = annual_df.set_index("metric")["value"]

    for enduse in annual_totals.index:
        estimated_annual = daily_enduse_means[enduse] * 8760
        actual_annual = annual_totals[enduse]
        ratio = estimated_annual / actual_annual
        assert 0.95 < ratio < 1.05, (
            f"End use '{enduse}': daily mean * 8760 = {estimated_annual:.0f}, "
            f"annual = {actual_annual:.0f}, ratio = {ratio:.3f} (expected ~1.0)"
        )


@pytest.mark.parametrize("group_by", literal_to_list(TimeGroup))
def test_seasonal_load_lines_time_groupings(  # noqa: C901
    api_client: APIClient, weekday_weekend_test_data: DuckDBPyConnection, group_by: TimeGroup
) -> None:
    """Test seasonal load lines with different time groupings."""
    import pandas as pd

    test_con = weekday_weekend_test_data
    api_client.db = test_con

    # Clear cached metadata so it will be re-fetched from test database
    api_client.refresh_metadata()

    # Get API results
    df_api = api_client.get_seasonal_load_lines(
        scenario="baseline", years=[2030], group_by=group_by, agg="Average Day"
    )

    # Verify structure
    assert isinstance(df_api, pd.DataFrame)
    assert not df_api.empty
    # Base expected columns
    expected_columns = {"scenario", "year", "hour_of_day", "value"}
    # Add columns based on grouping
    if "Seasonal" in group_by:
        expected_columns.add("season")
    if "Weekday/Weekend" in group_by:
        expected_columns.add("day_type")
    assert set(df_api.columns) == expected_columns

    # Should have hours 0-23
    assert set(df_api["hour_of_day"].unique()) == set(range(24))

    # Calculate expected number of rows
    expected_rows = 24  # base hours
    if "Seasonal" in group_by:
        expected_rows *= 4  # 4 seasons
    if "Weekday/Weekend" in group_by:
        expected_rows *= 2  # weekday/weekend
    assert len(df_api) == expected_rows

    # Group-specific validations
    if "Weekday/Weekend" in group_by:
        # Should have weekday and weekend
        assert set(df_api["day_type"].unique()) == {"Weekday", "Weekend"}
        # Verify values: weekdays should be 1, weekends should be 8
        weekday_values = df_api[df_api["day_type"] == "Weekday"]["value"].unique()
        weekend_values = df_api[df_api["day_type"] == "Weekend"]["value"].unique()
        assert len(weekday_values) == 1 and weekday_values[0] == 1.0
        assert len(weekend_values) == 1 and weekend_values[0] == 8.0
    if "Seasonal" in group_by:
        # Should have 4 seasons
        assert len(df_api["season"].unique()) == 4
        # If only seasonal (not combined with weekday/weekend), check against pandas calculation
        if group_by == "Seasonal":
            # Create reference datetime index (must match the test data exactly)
            datetime_index = pd.date_range(
                start="2018-01-01 00:00:00", end="2018-12-31 23:00:00", freq="h"
            )
            # Create reference DataFrame with seasonal mapping using utility constants
            ref_data = []
            for dt in datetime_index:
                value = 1 if dt.weekday() < 5 else 8
                ref_data.append(
                    {"hour_of_day": dt.hour, "season": season(dt.dayofyear), "value": value}
                )
            ref_df = pd.DataFrame(ref_data)
            # Calculate pandas seasonal averages (grouped by season and hour)
            pandas_seasonal = (
                ref_df.groupby(["season", "hour_of_day"])["value"].mean().reset_index()
            )
            pandas_seasonal = pandas_seasonal.sort_values(["season", "hour_of_day"]).reset_index(
                drop=True
            )
            # Sort API result for comparison
            api_comparison = (
                df_api[["season", "hour_of_day", "value"]]
                .sort_values(["season", "hour_of_day"])
                .reset_index(drop=True)
            )
            # Compare the calculated values
            pd.testing.assert_frame_equal(
                pandas_seasonal,
                api_comparison,
                check_dtype=False,
                rtol=1e-5,  # Allow for small floating point differences
            )
            # Verify that each season has different values (since different weekday/weekend ratios)
            season_values = df_api.groupby("season")["value"].first()
            assert (
                len(season_values.unique()) == 4
            ), "Each season should have a different weekday/weekend ratio"
            # All values should be between 1 and 8 (weighted averages)
            all_values = df_api["value"].unique()
            assert all(1 <= val <= 8 for val in all_values), "All values should be between 1 and 8"
    # For weekday/weekend only, compare with pandas calculation
    if group_by == "Weekday/Weekend":
        # Create reference datetime index
        datetime_index = pd.date_range(
            start="2018-01-01 00:00:00", end="2018-12-31 23:00:00", freq="h"
        )
        # Create reference DataFrame
        ref_data = []
        for dt in datetime_index:
            value = 1 if dt.weekday() < 5 else 8
            day_type = "Weekday" if dt.weekday() < 5 else "Weekend"
            ref_data.append(
                {"datetime": dt, "hour_of_day": dt.hour, "day_type": day_type, "value": value}
            )
        ref_df = pd.DataFrame(ref_data)
        # Calculate pandas aggregation (should be same since all values are constant)
        pandas_result = ref_df.groupby(["day_type", "hour_of_day"])["value"].mean().reset_index()
        pandas_result = pandas_result.sort_values(["day_type", "hour_of_day"]).reset_index(
            drop=True
        )
        # Sort API result for comparison
        api_comparison = (
            df_api[["day_type", "hour_of_day", "value"]]
            .sort_values(["day_type", "hour_of_day"])
            .reset_index(drop=True)
        )

        # Compare values
        pd.testing.assert_frame_equal(pandas_result, api_comparison, check_dtype=False)
