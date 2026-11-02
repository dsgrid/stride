"""Tests that temporal data are aligned in local standard time.

stride's time contract:
- Weather data are daily values whose timestamps are instants at the start of each
  local-standard-time day. Load shape hours (0-23) are in local standard time.
- energy_projection.timestamp is an absolute instant (TIMESTAMPTZ) and time_zone is the
  geography's standard time zone (no daylight saving time).
- Database sessions run in UTC. Local labels (date, month, weekday, hour of day) are derived
  explicitly with timezone(time_zone, timestamp), so results never depend on the machine.

Reference values are computed with pandas and zoneinfo, independently of the dbt SQL.
"""

import json
from pathlib import Path
from typing import Generator
from zoneinfo import ZoneInfo

import duckdb
import pandas as pd
import pytest
from pytest import TempPathFactory

from stride import Project
from stride.api import APIClient
from stride.api.utils import (
    FALL_DAY_END,
    FALL_DAY_START,
    SPRING_DAY_END,
    SPRING_DAY_START,
    format_utc_offset,
)
from stride.project import check_energy_projection_time_alignment

SECTOR_NAME_MAP = {
    "Industry": "Industrial",
    "Transport": "Transportation",
    "Service": "Commercial",
}


@pytest.fixture(scope="module")
def leap_year_project(tmp_path_factory: TempPathFactory) -> Generator[Project, None, None]:
    """Project for a second geography (east of UTC by 7 hours) with a leap weather year."""
    tmp_path = tmp_path_factory.mktemp("leap_year")
    config = {
        "project_id": "leap_year_project",
        "creator": "tester",
        "description": "Test project with a leap weather year.",
        "country": "country_2",
        "start_year": 2025,
        "end_year": 2030,
        "step_year": 5,
        "weather_year": 2020,
        "scenarios": [{"name": "baseline"}],
    }
    config_file = tmp_path / "leap_year_project.json5"
    config_file.write_text(json.dumps(config))
    # Project.create uses the APIClient singleton, which would otherwise switch the shared
    # session client to this project.
    orig = APIClient._instance
    APIClient._instance = None
    try:
        Project.create(config_file, base_dir=tmp_path, dataset="global-test").close()
    finally:
        APIClient._instance = orig
    with Project.load(tmp_path / "leap_year_project", read_only=True) as project:
        yield project


@pytest.fixture(params=["default_project", "leap_year_project"])
def project(request: pytest.FixtureRequest) -> Project:
    return request.getfixturevalue(request.param)


EXPECTED_TIME_ZONES = {"country_1": "Etc/GMT-1", "country_2": "Etc/GMT-7"}


def _expected_hours(project: Project) -> pd.DatetimeIndex:
    """Return every hour of the weather year in local standard time, as instants."""
    year = project.config.weather_year
    return pd.date_range(
        f"{year}-01-01 00:00", f"{year}-12-31 23:00", freq="h", tz=ZoneInfo(project.time_zone)
    )


def _read_weather_bait(project: Project) -> pd.DataFrame:
    """Return the daily BAIT for the weather year, labeled with local dates via zoneinfo."""
    df = project.con.sql(
        """
        SELECT timestamp, value AS bait
        FROM dsgrid_data.baseline__weather_bait__1_0_0
        WHERE geography = ? AND metric = 'BAIT'
        """,
        params=[project.config.country],
    ).df()
    local = df["timestamp"].dt.tz_convert(ZoneInfo(project.time_zone))
    df["local_date"] = local.dt.tz_localize(None)
    return df[local.dt.year == project.config.weather_year].reset_index(drop=True)


def test_session_time_zone_is_utc(project: Project) -> None:
    row = project.con.execute("SELECT current_setting('TimeZone')").fetchone()
    assert row is not None
    assert row[0] == "UTC"


def test_project_time_zone(project: Project) -> None:
    expected = EXPECTED_TIME_ZONES[project.config.country]
    assert project.time_zone == expected
    persisted = json.loads((project.path / "project.json5").read_text())
    assert persisted["time_zone"] == expected


def test_energy_projection_storage_contract(project: Project) -> None:
    types = {x[0]: x[1] for x in project.con.sql("DESCRIBE energy_projection").fetchall()}
    assert types["timestamp"] == "TIMESTAMP WITH TIME ZONE"
    assert types["time_zone"] == "VARCHAR"
    time_zones = project.con.sql("SELECT DISTINCT time_zone FROM energy_projection").fetchall()
    assert time_zones == [(project.time_zone,)]
    assert check_energy_projection_time_alignment(project.con, project.config) is None


def test_energy_projection_spans_local_weather_year(project: Project) -> None:
    """Every (scenario, model_year) covers exactly the weather year in local standard time."""
    expected = _expected_hours(project)
    assert len(expected) == (8784 if project.config.weather_year == 2020 else 8760)
    df = project.con.sql(
        "SELECT DISTINCT scenario, model_year, timestamp FROM energy_projection"
    ).df()
    for (scenario, model_year), group in df.groupby(["scenario", "model_year"]):
        actual = sorted(group["timestamp"])
        assert actual == list(expected), (scenario, model_year)


def test_weather_days_labeled_with_local_dates(project: Project) -> None:
    """Each weather day's month, day, and weekday/weekend come from its local date."""
    expected = _read_weather_bait(project)
    actual = project.con.sql(
        "SELECT timestamp, month, day, day_type, bait FROM baseline.temperature_multipliers"
    ).df()
    merged = expected.merge(actual, on="timestamp", how="outer", validate="one_to_one")
    assert len(merged) == len(expected) == (366 if project.config.weather_year == 2020 else 365)
    assert not merged.isna().any().any()
    assert (merged["month"] == merged["local_date"].dt.month).all()
    assert (merged["day"] == merged["local_date"].dt.day).all()
    is_weekend = merged["local_date"].dt.weekday >= 5  # Saturday=5, Sunday=6
    assert (merged["day_type"] == is_weekend.map({True: "weekend", False: "weekday"})).all()
    assert (merged["bait_x"] == merged["bait_y"]).all()


def test_hourly_values_follow_local_load_shapes(project: Project) -> None:
    """For end uses without temperature adjustment, every hourly value is the representative
    load shape value for its local month, weekday/weekend, and hour, times one scaling factor
    per sector. Any shift in hours, days, or months would break the constant ratio.
    """
    model_year = project.config.start_year
    tz = ZoneInfo(project.time_zone)
    actual = project.con.sql(
        """
        SELECT timestamp, sector, metric, value
        FROM energy_projection
        WHERE scenario = 'baseline' AND model_year = ? AND metric NOT IN ('heating', 'cooling')
        """,
        params=[model_year],
    ).df()
    shapes = project.con.sql(
        """
        SELECT sector, metric, month, hour, is_weekday, value AS shape_value
        FROM dsgrid_data.baseline__load_shapes__1_0_0
        WHERE geography = ? AND model_year = ?
        """,
        params=[project.config.country, model_year],
    ).df()
    shapes["sector"] = shapes["sector"].replace(SECTOR_NAME_MAP)

    local = actual["timestamp"].dt.tz_convert(tz)
    actual["month"] = local.dt.month
    actual["hour"] = local.dt.hour
    actual["is_weekday"] = local.dt.weekday < 5
    merged = actual.merge(shapes, on=["sector", "metric", "month", "hour", "is_weekday"])
    assert len(merged) == len(actual)
    merged = merged[merged["shape_value"] > 0]
    ratios = (merged["value"] / merged["shape_value"]).groupby(merged["sector"])
    assert (ratios.std() / ratios.mean()).max() < 1e-9


@pytest.fixture
def isolated_api_client(project: Project) -> Generator[APIClient, None, None]:
    """APIClient for the project that does not disturb the shared singleton."""
    orig = APIClient._instance
    APIClient._instance = None
    try:
        yield APIClient(project=project)
    finally:
        APIClient._instance = orig


def _season(day_of_year: int) -> str:
    if SPRING_DAY_START <= day_of_year < SPRING_DAY_END:
        return "Spring"
    if SPRING_DAY_END <= day_of_year < FALL_DAY_START:
        return "Summer"
    if FALL_DAY_START <= day_of_year < FALL_DAY_END:
        return "Fall"
    return "Winter"


def test_seasonal_hour_of_day_is_local(project: Project, isolated_api_client: APIClient) -> None:
    """The viewer's diurnal profiles use local standard hours, seasons, and weekdays."""
    model_year = project.config.start_year
    totals = project.con.sql(
        """
        SELECT timestamp, SUM(value) AS value
        FROM energy_projection
        WHERE scenario = 'baseline' AND model_year = ?
        GROUP BY timestamp
        """,
        params=[model_year],
    ).df()
    local = totals["timestamp"].dt.tz_convert(ZoneInfo(project.time_zone))
    totals["hour_of_day"] = local.dt.hour
    totals["season"] = [_season(x) for x in local.dt.dayofyear]
    totals["day_type"] = (local.dt.weekday >= 5).map({True: "Weekend", False: "Weekday"})
    keys = ["season", "day_type", "hour_of_day"]
    expected = totals.groupby(keys)["value"].mean().reset_index()

    actual = isolated_api_client.get_seasonal_load_lines(
        scenario="baseline",
        years=[model_year],
        group_by="Seasonal and Weekday/Weekend",
        agg="Average Day",
    )
    actual = actual[keys + ["value"]].sort_values(keys).reset_index(drop=True)
    expected = expected.sort_values(keys).reset_index(drop=True)
    pd.testing.assert_frame_equal(actual, expected, check_dtype=False, rtol=1e-9)


def test_results_do_not_depend_on_session_time_zone(
    project: Project, isolated_api_client: APIClient
) -> None:
    """Stored instants and API outputs are identical regardless of the session time zone,
    e.g., if another tool or a user's script opens the database in their machine's zone.
    """
    model_year = project.config.start_year
    client = isolated_api_client

    def collect() -> list[pd.DataFrame]:
        return [
            project.con.sql(
                "SELECT MIN(epoch_ms(timestamp)), MAX(epoch_ms(timestamp)) FROM energy_projection"
            ).df(),
            client.get_seasonal_load_lines(
                scenario="baseline",
                years=[model_year],
                group_by="Seasonal and Weekday/Weekend",
                agg="Average Day",
            ),
            client.get_time_series_comparison("baseline", model_year, resample="Daily Mean"),
            client.get_time_series_comparison("baseline", model_year, resample="Weekly Mean"),
            client.get_weather_metric("baseline", model_year, "BAIT", "Daily Mean"),
            client.get_weather_metric("baseline", model_year, "BAIT", "Weekly Mean"),
        ]

    expected = collect()
    try:
        for session_time_zone in ("America/Denver", "Pacific/Kiritimati", "Asia/Kolkata"):
            project.con.execute(f"SET TimeZone = '{session_time_zone}'")
            for actual, exp in zip(collect(), expected):
                pd.testing.assert_frame_equal(actual, exp)
    finally:
        project.con.execute("SET TimeZone = 'UTC'")


def test_weather_metric_uses_local_dates(project: Project, isolated_api_client: APIClient) -> None:
    expected = _read_weather_bait(project).sort_values("local_date").reset_index(drop=True)
    actual = isolated_api_client.get_weather_metric(
        "baseline", project.config.start_year, "BAIT", "Daily Mean"
    )
    assert list(actual["datetime"]) == list(expected["local_date"])
    assert list(actual["value"]) == pytest.approx(list(expected["bait"]))


def test_hour_of_day_label(isolated_api_client: APIClient) -> None:
    offset = {"Etc/GMT-1": "UTC+01:00", "Etc/GMT-7": "UTC+07:00"}[isolated_api_client.time_zone]
    assert isolated_api_client.hour_of_day_label == f"Hour of Day ({offset}, standard time)"


@pytest.mark.parametrize(
    "time_zone, expected",
    [
        ("Etc/GMT-1", "UTC+01:00"),
        ("Etc/GMT+5", "UTC-05:00"),
        ("Asia/Kolkata", "UTC+05:30"),
        ("Asia/Kathmandu", "UTC+05:45"),
        ("UTC", "UTC+00:00"),
    ],
)
def test_format_utc_offset(time_zone: str, expected: str) -> None:
    assert format_utc_offset(time_zone) == expected


def test_export_energy_projection(leap_year_project: Project, tmp_path: Path) -> None:
    """CSV timestamps carry the local standard offset; Parquet preserves the instants."""
    project = leap_year_project
    csv_file = tmp_path / "energy_projection.csv"
    parquet_file = tmp_path / "energy_projection.parquet"
    project.export_energy_projection(csv_file)
    project.export_energy_projection(parquet_file)

    first_rows = pd.read_csv(csv_file, nrows=1000)
    assert set(first_rows["time_zone"]) == {"Etc/GMT-7"}
    assert first_rows["timestamp"].str.endswith("+07").all()
    row = project.con.execute("SELECT current_setting('TimeZone')").fetchone()
    assert row is not None and row[0] == "UTC"

    query = "SELECT MIN(epoch_ms(timestamp)), MAX(epoch_ms(timestamp)), COUNT(*) FROM {}"
    expected = project.con.sql(query.format("energy_projection")).fetchone()
    with duckdb.connect() as con:
        from_parquet = con.sql(query.format(f"read_parquet('{parquet_file.as_posix()}')"))
        assert from_parquet.fetchone() == expected
        from_csv = con.sql(
            query.format(
                f"read_csv('{csv_file.as_posix()}', types={{'timestamp': 'TIMESTAMPTZ'}})"
            )
        )
        assert from_csv.fetchone() == expected


def test_legacy_energy_projection_detected(default_project: Project) -> None:
    config = default_project.config
    with duckdb.connect() as con:
        con.execute("SET TimeZone = 'UTC'")
        assert check_energy_projection_time_alignment(con, config) is None

        # Projection created before stride recorded time zones.
        con.execute("CREATE TABLE energy_projection (timestamp TIMESTAMPTZ, value DOUBLE)")
        msg = check_energy_projection_time_alignment(con, config)
        assert msg is not None and "re-create" in msg

        # Days shifted by one, as computed by older versions on machines west of the country.
        con.execute("DROP TABLE energy_projection")
        con.execute(
            """
            CREATE TABLE energy_projection AS
            SELECT
                range AS timestamp,
                'Etc/GMT-1' AS time_zone,
                1.0 AS value
            FROM range(
                TIMESTAMPTZ '2018-01-01 23:00:00+00',
                TIMESTAMPTZ '2019-01-01 23:00:00+00',
                INTERVAL 1 HOUR
            )
            """
        )
        msg = check_energy_projection_time_alignment(con, config)
        assert msg is not None and "2018-01-02 00:00:00" in msg


def test_duckdb_day_of_week_semantics() -> None:
    """DAYOFWEEK is 0-based from Sunday; ISODOW is 1-based from Monday. stride uses ISODOW."""
    with duckdb.connect() as con:
        row = con.execute(
            "SELECT DAYOFWEEK(DATE '2018-01-06'), DAYOFWEEK(DATE '2018-01-07'), "
            "ISODOW(DATE '2018-01-06'), ISODOW(DATE '2018-01-07'), ISODOW(DATE '2018-01-08')"
        ).fetchone()
    assert row == (6, 0, 6, 7, 1)  # Saturday, Sunday, Saturday, Sunday, Monday
