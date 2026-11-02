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
import shutil
from pathlib import Path
from typing import Generator, cast
from zoneinfo import ZoneInfo

import duckdb
import pandas as pd
import pytest
from chronify.exceptions import InvalidParameter
from pytest import TempPathFactory

from stride import Project
from stride.api import APIClient
from stride.api.utils import format_utc_offset
from stride.project import check_energy_projection_time_alignment, lookup_time_zone
from time_reference import season

EXPECTED_TIME_ZONES = {"country_1": "Etc/GMT-1", "country_2": "Etc/GMT-7"}


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
    return cast(Project, request.getfixturevalue(request.param))


@pytest.fixture
def api_client(project: Project) -> Generator[APIClient, None, None]:
    """APIClient for the project that does not disturb the shared singleton."""
    orig = APIClient._instance
    APIClient._instance = None
    try:
        yield APIClient(project=project)
    finally:
        APIClient._instance = orig


def _num_days(project: Project) -> int:
    return 366 if project.config.weather_year % 4 == 0 else 365


def _to_local(timestamps: pd.Series, project: Project) -> pd.Series:
    """Convert instants to naive local standard time with zoneinfo."""
    local: pd.Series = timestamps.dt.tz_convert(ZoneInfo(project.time_zone)).dt.tz_localize(None)
    return local


def _read_weather_bait(project: Project) -> pd.DataFrame:
    """Return the daily BAIT for the weather year, labeled with local dates."""
    df = project.con.sql(
        """
        SELECT timestamp, value AS bait
        FROM dsgrid_data.baseline__weather_bait__1_0_0
        WHERE geography = ? AND metric = 'BAIT'
        """,
        params=[project.config.country],
    ).df()
    df["local_date"] = _to_local(df["timestamp"], project)
    result: pd.DataFrame = df[df["local_date"].dt.year == project.config.weather_year]
    return result.sort_values("local_date").reset_index(drop=True)


def _read_hourly_totals(project: Project) -> pd.DataFrame:
    """Return total baseline load by hour for the first model year, labeled with local time."""
    df = project.con.sql(
        """
        SELECT timestamp, SUM(value) AS value
        FROM energy_projection
        WHERE scenario = 'baseline' AND model_year = ?
        GROUP BY timestamp
        """,
        params=[project.config.start_year],
    ).df()
    df["local_time"] = _to_local(df["timestamp"], project)
    return df


def test_time_metadata(project: Project) -> None:
    """The project records its zone, sessions run in UTC, and timestamps are instants."""
    expected = EXPECTED_TIME_ZONES[project.config.country]
    assert project.time_zone == expected
    assert json.loads((project.path / "project.json5").read_text())["time_zone"] == expected
    assert project.con.execute("SELECT current_setting('TimeZone')").fetchone() == ("UTC",)

    types = {x[0]: x[1] for x in project.con.sql("DESCRIBE energy_projection").fetchall()}
    assert types["timestamp"] == "TIMESTAMP WITH TIME ZONE"
    assert types["time_zone"] == "VARCHAR"
    time_zones = project.con.sql("SELECT DISTINCT time_zone FROM energy_projection").fetchall()
    assert time_zones == [(expected,)]
    assert check_energy_projection_time_alignment(project.con, project.config) is None


def test_energy_projection_spans_local_weather_year(project: Project) -> None:
    """Every (scenario, model_year) covers exactly the weather year in local standard time."""
    year = project.config.weather_year
    expected = list(
        pd.date_range(f"{year}-01-01 00:00", f"{year}-12-31 23:00", freq="h", tz=project.time_zone)
    )
    assert len(expected) == 24 * _num_days(project)
    df = project.con.sql(
        "SELECT DISTINCT scenario, model_year, timestamp FROM energy_projection"
    ).df()
    for (scenario, model_year), group in df.groupby(["scenario", "model_year"]):
        assert sorted(group["timestamp"]) == expected, (scenario, model_year)


def test_weather_days_labeled_with_local_dates(project: Project) -> None:
    """Each weather day's month, day, and weekday/weekend come from its local date."""
    expected = _read_weather_bait(project)
    actual = project.con.sql(
        "SELECT timestamp, month, day, day_type, bait FROM baseline.temperature_multipliers"
    ).df()
    merged = expected.merge(
        actual, on="timestamp", how="outer", validate="one_to_one", suffixes=("_ref", "")
    )
    assert len(merged) == _num_days(project)
    assert not merged.isna().any().any()
    local_date = merged["local_date"].dt
    assert (merged["month"] == local_date.month).all()
    assert (merged["day"] == local_date.day).all()
    is_weekend = local_date.weekday >= 5  # Saturday=5, Sunday=6
    assert (merged["day_type"] == is_weekend.map({True: "weekend", False: "weekday"})).all()
    assert (merged["bait"] == merged["bait_ref"]).all()


def test_hourly_values_follow_local_load_shapes(project: Project) -> None:
    """For end uses without temperature adjustment, every hourly value is the representative
    load shape value for its local month, weekday/weekend, and hour, times one scaling factor
    per sector. Any shift in hours, days, or months would break the constant ratio.
    """
    model_year = project.config.start_year
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

    local = _to_local(actual["timestamp"], project).dt
    actual["month"] = local.month
    actual["hour"] = local.hour
    actual["is_weekday"] = local.weekday < 5
    merged = actual.merge(shapes, on=["sector", "metric", "month", "hour", "is_weekday"])
    assert len(merged) == len(actual)
    merged = merged[merged["shape_value"] > 0]
    ratios = (merged["value"] / merged["shape_value"]).groupby(merged["sector"])
    assert (ratios.std() / ratios.mean()).max() < 1e-9


def test_seasonal_profiles_use_local_time(project: Project, api_client: APIClient) -> None:
    """The viewer's diurnal profiles use local standard hours, seasons, and weekdays."""
    totals = _read_hourly_totals(project)
    local = totals["local_time"].dt
    totals["hour_of_day"] = local.hour
    totals["season"] = [season(x) for x in local.dayofyear]
    totals["day_type"] = (local.weekday >= 5).map({True: "Weekend", False: "Weekday"})
    keys = ["season", "day_type", "hour_of_day"]
    expected = totals.groupby(keys)["value"].mean().reset_index()

    actual = api_client.get_seasonal_load_lines(
        scenario="baseline",
        years=[project.config.start_year],
        group_by="Seasonal and Weekday/Weekend",
        agg="Average Day",
    )
    actual = actual[keys + ["value"]].sort_values(keys).reset_index(drop=True)
    expected = expected.sort_values(keys).reset_index(drop=True)
    pd.testing.assert_frame_equal(actual, expected, check_dtype=False, rtol=1e-9)

    offset = format_utc_offset(project.time_zone)
    assert api_client.hour_of_day_label == f"Hour of Day ({offset}, standard time)"


def test_daily_series_align_with_weather(project: Project, api_client: APIClient) -> None:
    """Day n of the daily load series and day n of the daily weather series are both the
    n-th local date of the weather year, so the viewer's weather overlay lines up.
    """
    model_year = project.config.start_year
    num_days = _num_days(project)
    totals = _read_hourly_totals(project)
    expected = totals.groupby(totals["local_time"].dt.dayofyear)["value"].mean()

    daily = api_client.get_time_series_comparison("baseline", model_year, resample="Daily Mean")
    assert list(daily["time_period"]) == list(range(1, num_days + 1))
    assert list(daily["value"]) == pytest.approx(list(expected))

    weather = api_client.get_weather_metric("baseline", model_year, "BAIT", "Daily Mean")
    assert list(weather["datetime"]) == list(_read_weather_bait(project)["local_date"])
    assert list(weather["datetime"].dt.dayofyear) == list(range(1, num_days + 1))

    weekly = api_client.get_time_series_comparison("baseline", model_year, resample="Weekly Mean")
    assert list(weekly["time_period"]) == list(range(1, 54))


def test_results_do_not_depend_on_session_time_zone(
    project: Project, api_client: APIClient
) -> None:
    """Stored instants and API outputs are identical regardless of the session time zone,
    e.g., if another tool or a user's script opens the database in their machine's zone.
    """
    model_year = project.config.start_year

    def collect() -> list[pd.DataFrame]:
        return [
            project.con.sql(
                "SELECT MIN(epoch_ms(timestamp)), MAX(epoch_ms(timestamp)) FROM energy_projection"
            ).df(),
            api_client.get_seasonal_load_lines(
                scenario="baseline",
                years=[model_year],
                group_by="Seasonal and Weekday/Weekend",
                agg="Average Day",
            ),
            api_client.get_time_series_comparison("baseline", model_year, resample="Daily Mean"),
            api_client.get_time_series_comparison("baseline", model_year, resample="Weekly Mean"),
            api_client.get_weather_metric("baseline", model_year, "BAIT", "Daily Mean"),
            api_client.get_weather_metric("baseline", model_year, "BAIT", "Weekly Mean"),
        ]

    expected = collect()
    try:
        for session_time_zone in ("America/Denver", "Pacific/Kiritimati", "Asia/Kolkata"):
            project.con.execute(f"SET TimeZone = '{session_time_zone}'")
            for actual, exp in zip(collect(), expected):
                pd.testing.assert_frame_equal(actual, exp)
    finally:
        project.con.execute("SET TimeZone = 'UTC'")


def test_api_uses_project_time_zone_without_column(
    project: Project, api_client: APIClient
) -> None:
    """Tables from projects created before stride stored time zones have no time_zone column,
    so the API falls back to the project's time zone and returns the same results.
    """
    model_year = project.config.start_year

    def collect() -> list[pd.DataFrame]:
        return [
            api_client.get_seasonal_load_lines(
                scenario="baseline", years=[model_year], group_by="Seasonal", agg="Average Day"
            ),
            api_client.get_time_series_comparison("baseline", model_year, resample="Daily Mean"),
        ]

    assert api_client._time_zone_for("energy_projection") is None
    expected = collect()
    old_table = (
        project.get_energy_projection("baseline")
        .filter(f"model_year = {model_year}")
        .select("* EXCLUDE (time_zone)")
        .df()
    )
    with duckdb.connect() as con:
        con.execute("SET TimeZone = 'UTC'")
        con.register("old_table", old_table)
        con.execute("CREATE TABLE energy_projection AS SELECT * FROM old_table")
        api_client.db = con
        assert api_client._time_zone_for("energy_projection") == project.time_zone
        for actual, exp in zip(collect(), expected):
            pd.testing.assert_frame_equal(actual, exp)


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
    assert project.con.execute("SELECT current_setting('TimeZone')").fetchone() == ("UTC",)

    query = "SELECT MIN(epoch_ms(timestamp)), MAX(epoch_ms(timestamp)), COUNT(*) FROM {}"
    expected = project.con.sql(query.format("energy_projection")).fetchone()
    csv_table = f"read_csv('{csv_file.as_posix()}', types={{'timestamp': 'TIMESTAMPTZ'}})"
    with duckdb.connect() as con:
        assert con.sql(query.format(f"read_parquet('{parquet_file.as_posix()}')")).fetchone() == (
            expected
        )
        assert con.sql(query.format(csv_table)).fetchone() == expected


def test_load_fills_in_missing_time_zone(leap_year_project: Project, tmp_path: Path) -> None:
    """Projects created before stride stored time zones get one when they are loaded."""
    project_dir = tmp_path / "old_project"
    shutil.copytree(leap_year_project.path, project_dir)
    config_file = project_dir / "project.json5"
    config = json.loads(config_file.read_text())
    del config["time_zone"]
    config_file.write_text(json.dumps(config))
    with Project.load(project_dir, read_only=True) as project:
        assert project.time_zone == "Etc/GMT-7"


@pytest.mark.parametrize(
    "time_zones, expected_error",
    [([], True), (["Etc/GMT-1"], False), (["Etc/GMT-1", "Etc/GMT-2"], True)],
)
def test_lookup_time_zone(time_zones: list[str], expected_error: bool) -> None:
    with duckdb.connect() as con:
        con.execute("CREATE SCHEMA dsgrid_data")
        con.execute(
            "CREATE TABLE dsgrid_data.baseline__weather_bait__1_0_0 "
            "(geography VARCHAR, time_zone VARCHAR)"
        )
        for time_zone in time_zones:
            con.execute(
                "INSERT INTO dsgrid_data.baseline__weather_bait__1_0_0 VALUES ('a', ?)",
                [time_zone],
            )
        if expected_error:
            with pytest.raises(InvalidParameter):
                lookup_time_zone(con, "a")
        else:
            assert lookup_time_zone(con, "a") == time_zones[0]


@pytest.mark.parametrize(
    "create_table, expected_in_message",
    [
        pytest.param(None, None, id="no_table"),
        pytest.param(
            "CREATE TABLE energy_projection (timestamp TIMESTAMPTZ, value DOUBLE)",
            "re-create",
            id="no_time_zone_column",
        ),
        pytest.param(
            # Days shifted by one, as computed by older versions on machines west of the
            # country.
            """
            CREATE TABLE energy_projection AS
            SELECT range AS timestamp, 'Etc/GMT-1' AS time_zone, 1.0 AS value
            FROM range(
                TIMESTAMPTZ '2018-01-01 23:00:00+00',
                TIMESTAMPTZ '2019-01-01 23:00:00+00',
                INTERVAL 1 HOUR
            )
            """,
            "2018-01-02 00:00:00",
            id="shifted_days",
        ),
    ],
)
def test_legacy_energy_projection_detected(
    default_project: Project, create_table: str | None, expected_in_message: str | None
) -> None:
    with duckdb.connect() as con:
        con.execute("SET TimeZone = 'UTC'")
        if create_table is not None:
            con.execute(create_table)
        msg = check_energy_projection_time_alignment(con, default_project.config)
    if expected_in_message is None:
        assert msg is None
    else:
        assert msg is not None and expected_in_message in msg
