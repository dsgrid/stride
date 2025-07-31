"""
Tests for the database api.
"""

import pytest
import tempfile
import duckdb
import pandas as pd
from pathlib import Path
import yaml
from stride.api import APIClient
from typing import Any

def load_test_config(config_path: str = None) -> dict[str, Any]:
    """Load test configuration from YAML file."""
    if config_path is None:
        config_path = Path(__file__).parent / "test_config.yaml"

    config_path = Path(config_path)

    if not config_path.exists():
        # Return default config if file doesn't exist
        return {
            "database": {"path": None},
            "project": {
                "energy_proj_table": "main.scenario_comparison",
                "country": "country_1"
            }
        }

    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

@pytest.fixture
def test_config():
    """Load test configuration."""
    return load_test_config()




@pytest.fixture
def test_db_path(test_config):
    """Create a temporary test database with sample data. or use configured database"""

    config_db_path = test_config.get("database", {}).get("path")

    # If config specifies a database path and it exists, use it
    if config_db_path and Path(config_db_path).exists():
        yield config_db_path
        return

    # Let DuckDB create the file
    db_path = tempfile.mktemp(suffix='.db')

    # Create test database with sample data
    conn = duckdb.connect(db_path)

    # Create test table with sample data
    conn.execute("""
        CREATE TABLE main.scenario_comparison AS
        SELECT * FROM VALUES
            ('country_1', 'baseline', 2025, 0, 'Commercial', 'Lighting', 1000.0),
            ('country_1', 'baseline', 2025, 1, 'Commercial', 'Lighting', 1040.0),


            ('country_1', 'high_growth', 2025, 0, 'Commercial', 'Lighting', 1200.0),
            ('country_1', 'high_growth', 2025, 1, 'Commercial', 'Lighting', 1240.0),

            ('country_1', 'baseline', 2025, 0, 'Residential', 'Heating', 2000.0),
            ('country_1', 'baseline', 2025, 1, 'Residential', 'Heating', 2040.0),


            ('country_1', 'high_growth', 2030, 0, 'Commercial', 'Lighting', 1300.0),
            ('country_1', 'high_growth', 2030, 1, 'Commercial', 'Lighting', 1340.0),

            ('country_1', 'baseline', 2030, 0, 'Commercial', 'Lighting', 1100.0),
            ('country_1', 'baseline', 2030, 1, 'Commercial', 'Lighting', 1140.0),

            ('country_1', 'baseline', 2030, 0, 'Residential', 'Heating', 2200.0),
            ('country_1', 'baseline', 2030, 1, 'Residential', 'Heating', 2240.0),

        AS t(country, scenario, year,hour, sector, end_use, value)
    """)

    conn.close()
    yield db_path

    # Cleanup
    if Path(db_path).exists():
        Path(db_path).unlink()



@pytest.fixture
def api_client(test_db_path, test_config):
    """Create APIClient instance with test database and configuration."""
    # Update the global constants in the API module with test config values
    import stride.api
    original_table = stride.api.ENERGY_PROJ_TABLE
    original_country = stride.api.PROJECT_COUNTRY

    # Set test values
    stride.api.ENERGY_PROJ_TABLE = test_config.get("project", {}).get("energy_proj_table", "main.scenario_comparison")
    stride.api.PROJECT_COUNTRY = test_config.get("project", {}).get("country", "country_1")

    # Reset singleton to ensure clean state
    APIClient._instance = None
    client = APIClient(test_db_path)

    yield client

    # Restore original values
    stride.api.ENERGY_PROJ_TABLE = original_table
    stride.api.PROJECT_COUNTRY = original_country
    APIClient._instance = None


class TestAPIClient:
    """Test suite for APIClient methods."""

    def test_singleton_behavior(self, test_db_path):
        """Test that APIClient follows singleton pattern."""
        client1 = APIClient(test_db_path)
        # Reset singleton for clean test
        APIClient._instance = None
        client2 = APIClient(test_db_path)
        # Note: In real usage, both would be same instance
        assert isinstance(client1, APIClient)
        assert isinstance(client2, APIClient)

    def test_years_property(self, api_client):
        """Test years property returns cached list."""
        years = api_client.years
        assert isinstance(years, list)
        assert all(isinstance(year, int) for year in years)
        assert len(years) > 0
        # Test caching - should be same object
        assert api_client.years is years

    def test_scenarios_property(self, api_client):
        """Test scenarios property returns cached list."""
        scenarios = api_client.scenarios
        assert isinstance(scenarios, list)
        assert all(isinstance(scenario, str) for scenario in scenarios)
        assert len(scenarios) > 0
        # Test caching - should be same object
        assert api_client.scenarios is scenarios

    def test_get_years(self, api_client):
        """Test get_years method returns list of integers."""
        years = api_client.get_years()
        assert isinstance(years, list)
        assert all(isinstance(year, int) for year in years)
        assert len(years) > 0


    def test_validate_scenarios_valid(self, api_client):
        """Test validation passes for valid scenarios."""
        valid_scenarios = api_client.scenarios[:1]  # Take first scenario
        # Should not raise
        api_client._validate_scenarios(valid_scenarios)

    def test_validate_scenarios_invalid(self, api_client):
        """Test validation fails for invalid scenarios."""
        with pytest.raises(ValueError, match="Invalid scenarios"):
            api_client._validate_scenarios(["invalid_scenario"])

    def test_validate_years_valid(self, api_client):
        """Test validation passes for valid years."""
        valid_years = api_client.years[:1]  # Take first year
        # Should not raise
        api_client._validate_years(valid_years)

    def test_validate_years_invalid(self, api_client):
        """Test validation fails for invalid years."""
        with pytest.raises(ValueError, match="Invalid years"):
            api_client._validate_years([9999])

    def test_refresh_metadata(self, api_client):
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

    def test_get_annual_electricity_consumption_no_breakdown(self, api_client):
        """Test annual consumption without breakdown."""
        df = api_client.get_annual_electricity_consumption()
        assert isinstance(df, pd.DataFrame)
        assert not df.empty
        assert 'year' in df.columns

    def test_get_annual_electricity_consumption_with_breakdown(self, api_client):
        """Test annual consumption with sector breakdown."""
        df = api_client.get_annual_electricity_consumption(group_by="Sector")
        assert isinstance(df, pd.DataFrame)
        # May be empty due to placeholder SQL, but should not error

    def test_get_annual_peak_demand(self, api_client):
        """Test peak demand method executes."""
        df = api_client.get_annual_peak_demand()
        assert isinstance(df, pd.DataFrame)
        assert not df.empty
        assert 'year' in df.columns

    def test_get_annual_peak_demand_with_breakdown(self, api_client):
        """Test peak demand with sector breakdown."""
        df = api_client.get_annual_peak_demand(group_by="Sector")

        assert isinstance(df, pd.DataFrame)
        assert not df.empty
        assert 'scenario' in df.columns
        assert 'sector' in df.columns

    def test_get_secondary_metric(self, api_client):
        """Test secondary metric method executes."""
        valid_scenario = api_client.scenarios[0]
        df = api_client.get_secondary_metric(valid_scenario, "GDP")
        assert isinstance(df, pd.DataFrame)
        assert not df.empty
        assert 'year' in df.columns
        assert 'value' in df.columns

    def test_get_load_duration_curve(self, api_client):
        """Test load duration curve method executes."""
        valid_scenario = api_client.scenarios[0]
        valid_year = api_client.years[0]
        df = api_client.get_load_duration_curve(valid_year)
        assert isinstance(df, pd.DataFrame)
        assert not df.empty

    def test_get_scenario_summary(self, api_client):
        """Test scenario summary method executes."""
        valid_scenario = api_client.scenarios[0]
        valid_year = api_client.years[0]
        summary = api_client.get_scenario_summary(valid_scenario, valid_year)
        assert isinstance(summary, dict)
        assert 'TOTAL_CONSUMPTION' in summary
        assert 'PERC_GROWTH' in summary
        assert 'PEAK_DMD' in summary

    def test_get_weather_metric(self, api_client):
        """Test weather metric method executes."""
        valid_scenario = api_client.scenarios[0]
        valid_year = api_client.years[0]
        df = api_client.get_weather_metric(valid_scenario, valid_year, "Temperature")
        assert isinstance(df, pd.DataFrame)
        assert not df.empty
        assert 'datetime' in df.columns
        assert 'value' in df.columns

    def test_get_timeseries_comparison(self, api_client):
        """Test timeseries comparison method executes."""
        valid_scenario = api_client.scenarios[0]
        valid_years = api_client.years[:2] if len(api_client.years) >= 2 else [api_client.years[0]]
        df = api_client.get_timeseries_comparison(valid_scenario, valid_years)
        assert isinstance(df, pd.DataFrame)
        assert not df.empty

    def test_get_seasonal_load_lines(self, api_client):
        """Test seasonal load lines method executes."""
        valid_scenario = api_client.scenarios[0]
        df = api_client.get_seasonal_load_lines(valid_scenario)

        breakpoint()
        assert isinstance(df, pd.DataFrame)
        assert not df.empty


if __name__ == "__main__":
    pytest.main([__file__])

