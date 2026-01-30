"""Tests for shoulder month smoothing in temperature multipliers."""

import duckdb
import pandas as pd
from stride import Project


def _find_shoulder_months(multipliers: pd.DataFrame) -> tuple[list[int], list[int]]:
    """Find shoulder months with mixed zero and non-zero degree days.

    Returns
    -------
    tuple[list[int], list[int]]
        (shoulder_heating_months, shoulder_cooling_months)
    """
    shoulder_heating_months = []
    shoulder_cooling_months = []

    for month in multipliers["month"].unique():
        month_data = multipliers[multipliers["month"] == month]

        # Check for shoulder heating months
        if (month_data["total_hdd"] > 0).any():
            has_zero_hdd = (month_data["hdd"] == 0).any()
            has_nonzero_hdd = (month_data["hdd"] > 0).any()
            if has_zero_hdd and has_nonzero_hdd:
                shoulder_heating_months.append(month)

        # Check for shoulder cooling months
        if (month_data["total_cdd"] > 0).any():
            has_zero_cdd = (month_data["cdd"] == 0).any()
            has_nonzero_cdd = (month_data["cdd"] > 0).any()
            if has_zero_cdd and has_nonzero_cdd:
                shoulder_cooling_months.append(month)

    return shoulder_heating_months, shoulder_cooling_months


def _verify_heating_smoothing(multipliers: pd.DataFrame, month: int) -> None:
    """Verify that heating smoothing works correctly for a shoulder month."""
    month_data = multipliers[(multipliers["month"] == month) & (multipliers["total_hdd"] > 0)]

    zero_hdd_days = month_data[month_data["hdd"] == 0]
    if zero_hdd_days.empty:
        return

    # Days with HDD=0 should still have positive heating_multipliers due to smoothing
    assert (zero_hdd_days["heating_multiplier"] > 0).all(), (
        f"Month {month}: Days with HDD=0 should have positive heating_multiplier "
        f"due to shoulder month smoothing"
    )

    # The multiplier should be relatively small (less than the average)
    avg_multiplier = month_data["heating_multiplier"].mean()
    assert (
        zero_hdd_days["heating_multiplier"] < avg_multiplier
    ).all(), f"Month {month}: Smoothed heating_multipliers should be below average"


def _verify_cooling_smoothing(multipliers: pd.DataFrame, month: int) -> None:
    """Verify that cooling smoothing works correctly for a shoulder month."""
    month_data = multipliers[(multipliers["month"] == month) & (multipliers["total_cdd"] > 0)]

    zero_cdd_days = month_data[month_data["cdd"] == 0]
    if zero_cdd_days.empty:
        return

    # Days with CDD=0 should still have positive cooling_multipliers due to smoothing
    assert (zero_cdd_days["cooling_multiplier"] > 0).all(), (
        f"Month {month}: Days with CDD=0 should have positive cooling_multiplier "
        f"due to shoulder month smoothing"
    )

    # The multiplier should be relatively small (less than the average)
    avg_multiplier = month_data["cooling_multiplier"].mean()
    assert (
        zero_cdd_days["cooling_multiplier"] < avg_multiplier
    ).all(), f"Month {month}: Smoothed cooling_multipliers should be below average"


def test_shoulder_month_smoothing_prevents_spikes(default_project: Project) -> None:
    """Verify that shoulder month smoothing prevents unrealistic load spikes.

    In shoulder months (e.g., spring/fall), some days may have zero HDD/CDD while others
    have positive values. Without smoothing, this concentrates all load on the non-zero
    days, creating unrealistic spikes. With smoothing, zero-degree-day days are assigned
    a small value (min_degree_days / smoothing_factor) to distribute load more evenly.
    """
    project = default_project
    con = project.con

    # Query the temperature_multipliers view from the baseline scenario
    multipliers = con.sql(
        """
        SELECT
            geography,
            month,
            day_type,
            hdd,
            cdd,
            total_hdd,
            total_cdd,
            heating_multiplier,
            cooling_multiplier
        FROM baseline.temperature_multipliers
        ORDER BY month, timestamp
        """
    ).to_df()

    # Find shoulder months - months where there's a mix of zero and non-zero degree days
    shoulder_heating_months, shoulder_cooling_months = _find_shoulder_months(multipliers)

    # Verify smoothing works for shoulder heating months
    for month in shoulder_heating_months:
        _verify_heating_smoothing(multipliers, month)

    # Verify smoothing works for shoulder cooling months
    for month in shoulder_cooling_months:
        _verify_cooling_smoothing(multipliers, month)


def test_shoulder_month_smoothing_configuration(tmp_path) -> None:
    """Test that shoulder month smoothing parameters can be configured in ProjectConfig."""
    from stride.models import ModelParameters, ProjectConfig

    # Test default values
    params = ModelParameters()
    assert params.enable_shoulder_month_smoothing is True
    assert params.shoulder_month_smoothing_factor == 5.0

    # Test custom values
    params_custom = ModelParameters(
        enable_shoulder_month_smoothing=False, shoulder_month_smoothing_factor=10.0
    )
    assert params_custom.enable_shoulder_month_smoothing is False
    assert params_custom.shoulder_month_smoothing_factor == 10.0

    # Test in ProjectConfig
    config = ProjectConfig(
        project_id="test",
        creator="tester",
        description="Test project",
        country="USA",
        start_year=2025,
        end_year=2030,
        weather_year=2018,
        model_parameters=ModelParameters(
            enable_shoulder_month_smoothing=True, shoulder_month_smoothing_factor=2.0
        ),
    )
    assert config.model_parameters.enable_shoulder_month_smoothing is True
    assert config.model_parameters.shoulder_month_smoothing_factor == 2.0


def test_non_shoulder_months_unchanged() -> None:
    """Verify that non-shoulder months (all heating or all cooling) are unaffected by smoothing.

    In pure winter months (all days have HDD>0) or pure summer months (all days have CDD>0),
    the smoothing logic should have no effect since there are no zero-degree-day days to smooth.
    """
    # Create synthetic test data representing a pure winter month
    # All days have positive HDD, no zero days
    con = duckdb.connect(":memory:")

    # Create weather data for a cold month (January) - all days have heating
    dates = pd.date_range("2018-01-01", "2018-01-31", freq="D")
    winter_data = pd.DataFrame(
        {
            "geography": "test_country",
            "timestamp": dates,
            "weather_year": 2018,
            "month": 1,
            "day": dates.day,
            "day_type": ["weekday" if d < 5 else "weekend" for d in dates.dayofweek],
            "bait": [5.0 + i % 5 for i in range(len(dates))],  # All below 18°C
            "hdd": [13.0 - (i % 5) for i in range(len(dates))],  # All positive
            "cdd": [0.0] * len(dates),  # No cooling
        }
    )

    con.register("weather_data", winter_data)

    # Calculate multipliers with the same logic as temperature_multipliers.sql
    result = con.sql(
        """
        WITH grouped AS (
            SELECT
                geography,
                month,
                day_type,
                COUNT(*) AS num_days,
                SUM(hdd) AS total_hdd,
                SUM(cdd) AS total_cdd,
                MIN(CASE WHEN hdd > 0 THEN hdd END) AS min_hdd
            FROM weather_data
            GROUP BY geography, month, day_type
        )
        SELECT
            wd.day,
            wd.hdd,
            g.min_hdd,
            g.total_hdd,
            -- Without smoothing
            (wd.hdd / g.total_hdd) * g.num_days AS multiplier_no_smoothing,
            -- With smoothing (should be identical since no zero HDD days)
            (CASE WHEN g.total_hdd > 0 AND wd.hdd = 0
                  THEN g.min_hdd / 5.0
                  ELSE wd.hdd END / g.total_hdd) * g.num_days AS multiplier_with_smoothing
        FROM weather_data wd
        JOIN grouped g ON wd.geography = g.geography
                      AND wd.month = g.month
                      AND wd.day_type = g.day_type
    """
    ).to_df()

    # In pure winter months, smoothing should have no effect
    # (no zero HDD days to smooth)
    assert (result["multiplier_no_smoothing"] == result["multiplier_with_smoothing"]).all()

    # All HDDs are positive
    assert (result["hdd"] > 0).all()

    con.close()


def test_multipliers_sum_to_num_days(default_project: Project) -> None:
    """Verify that temperature multipliers properly sum to num_days within each group.

    This is critical for energy conservation - the sum of multipliers across all days
    in a group (month + day_type) should equal the number of days in that group.
    This must hold true even with shoulder month smoothing applied.
    """
    project = default_project
    con = project.con

    # Check that multipliers sum correctly for each group
    sums = con.sql(
        """
        SELECT
            month,
            day_type,
            MAX(num_days) AS num_days,
            SUM(heating_multiplier) AS sum_heating_multipliers,
            SUM(cooling_multiplier) AS sum_cooling_multipliers,
            -- Allow small numerical tolerance (0.01%)
            ABS(SUM(heating_multiplier) - MAX(num_days)) < MAX(num_days) * 0.0001 AS heating_ok,
            ABS(SUM(cooling_multiplier) - MAX(num_days)) < MAX(num_days) * 0.0001 AS cooling_ok
        FROM baseline.temperature_multipliers
        GROUP BY month, day_type
        ORDER BY month, day_type
        """
    ).to_df()

    # All groups should have multipliers summing to num_days
    assert sums[
        "heating_ok"
    ].all(), f"Heating multipliers don't sum to num_days:\n{sums[~sums['heating_ok']]}"
    assert sums[
        "cooling_ok"
    ].all(), f"Cooling multipliers don't sum to num_days:\n{sums[~sums['cooling_ok']]}"
