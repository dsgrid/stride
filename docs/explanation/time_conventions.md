(time-conventions)=
# Time Conventions

STRIDE produces hourly load for a full weather year. This page explains which time zone each piece of data is in, how STRIDE keeps hours and days aligned, and how you can check a project yourself.

**In short:** STRIDE works in each country's **local standard time**, which is a fixed UTC offset with no daylight saving time (DST). Hourly timestamps are stored as absolute instants (UTC). The viewer, the data API, and CSV exports show them in local standard time and name the offset, for example `UTC+01:00` for Germany.

## The project time zone

When you create a project, STRIDE looks up the country's standard time zone in the weather data and records it in `project.json5`:

```json5
{
  country: "Germany",
  weather_year: 2018,
  time_zone: "Etc/GMT-1",  // set by STRIDE; do not edit
  // ...
}
```

`Etc/GMT-1` is the IANA name for a fixed offset of UTC+01:00. The sign is inverted by POSIX convention. Germany observes summer time (UTC+02:00) from late March to late October, but STRIDE does not. A summer evening peak that happens at 19:00 on German clocks therefore appears at **18:00** in STRIDE.

## Input data

| Dataset | Time resolution | Time convention |
|---|---|---|
| Weather (`weather_bait`) | Daily, weather years 1995–2024 | Each value covers one local-standard-time day. The timestamp is the instant that day starts, e.g. `2018-01-01 00:00` in `Etc/GMT-1`, which is `2017-12-31 23:00` UTC. |
| Load shapes (`load_shapes`, IMAGE) | One weekday and one weekend day per month, 24 hours each | Hours 0–23 are hour-beginning, in local standard time. Hour 0 is 00:00–01:00. |
| Annual data (GDP, population, HDI, energy intensity, EV inputs) | Annual | No time of day. |

The IMAGE load shapes are not labeled with a time zone in their source. The shapes themselves show they are in local standard time:
- **Local, not UTC:** the residential evening peak falls around 19:00–20:00 in regions as far apart as Germany, India, Brazil, and Canada. If the hours were UTC, those peaks would be spread across the day by each region's offset.
- **Standard time, not clock time:**
  - The residential lighting profiles turn on and off with daylight. Compare months that have almost the same sunrise in solar terms but differ in DST, such as March and September.
  - The morning lighting ends *earlier* in the DST month, which matches local standard time. If the hours were clock time (with DST), it would end *later*.

## How STRIDE builds hourly data

The data become hourly in the `load_shapes_expanded` dbt model. For each day of the weather year:

1. **Label the day in local standard time.** `weather_bait_daily` converts the weather timestamp to the local date. From that date it takes the month, the day of month, and weekday or weekend (Saturday and Sunday are weekend days).
2. **Pick the representative day.** The month and weekday/weekend select the matching IMAGE load shape and temperature multiplier. For example, Tuesday 2018-01-02 uses the January weekday shape.
3. **Place the 24 hours.** Load shape hour *h* is assigned to local standard time *h*:00 on that date. It is then stored as an absolute instant (`TIMESTAMPTZ`).

A non-leap weather year produces 8760 hours, and a leap year produces 8784.

## Storage

The `energy_projection` table has two time columns:

| Column | Type | Meaning |
|---|---|---|
| `timestamp` | `TIMESTAMP WITH TIME ZONE` | Absolute instant at the start of the hour (period-beginning). DuckDB stores it as UTC. |
| `time_zone` | `VARCHAR` | The geography's standard time zone, e.g. `Etc/GMT-1`. |

Storing instants keeps the data unambiguous. Every tool that reads them agrees on which hour is which. If STRIDE later supports projects with several regions, their hours will also add up correctly even when the regions are in different time zones.

```{note}
DuckDB *displays* a `TIMESTAMPTZ` in the session's time zone. STRIDE runs its sessions in UTC, so tables printed by `stride calculated-tables show` display UTC values such as `2017-12-31 23:00:00+00`. That is the same instant as `2018-01-01 00:00:00+01`.
```

## Display and export

- **Viewer (`stride view`):** hour-of-day axes show local standard time with the offset, e.g. *Hour of Day (UTC+01:00, standard time)*. Seasons and weekday/weekend groupings also use local dates.
- **Data API (`stride.api.APIClient`):** `hour_of_day`, `time_period` (day or week of the year), seasons, weekday/weekend, and weather `datetime` values are all in local standard time. `APIClient.time_zone` returns the zone.
- **CSV export:** timestamps are written in local standard time with an explicit offset, e.g. `2018-01-01 00:00:00+01`, along with the `time_zone` column.
- **Parquet export:** timestamps are UTC-adjusted instants. Most tools show them in UTC or in your computer's time zone. Use the `time_zone` column to convert them.

To work with local times in pandas:

```python
df = project.get_energy_projection().df()
df["local_time"] = df["timestamp"].dt.tz_convert(project.time_zone)  # standard time, e.g. UTC+01:00
df["clock_time"] = df["timestamp"].dt.tz_convert("Europe/Berlin")  # local clock time with DST
```

## Check your project

1. **Time zone:** open `project.json5` and confirm that `time_zone` is the standard time zone you expect for the country.
2. **Year span:** the first and last local hours should be January 1 00:00 and December 31 23:00 of the weather year, with 8760 hours (8784 in a leap year):

   ```python
   from stride import Project

   with Project.load("my_project", read_only=True) as project:
       print(project.con.sql("""
           SELECT MIN(timezone(time_zone, timestamp)) AS first_hour,
                  MAX(timezone(time_zone, timestamp)) AS last_hour,
                  COUNT(DISTINCT timestamp) AS num_hours
           FROM energy_projection
       """))
   ```

3. **Daily shape:** in the viewer's seasonal plots, look for a plausible daily cycle. Typically that's an overnight minimum around 03:00–04:00, a morning ramp, and an evening peak. Remember that summer peaks appear one hour earlier than clock time in countries that observe DST.

## Projects created with older versions of STRIDE

STRIDE versions before this change derived dates and hours in the time zone of the computer they ran on. Whenever that zone was behind the country's, every weather day was labeled with the previous date. For example, a German project built on a computer in the Americas dropped January 1 and added January 1 of the following year. Separately, days labeled Sunday were treated as weekdays. The viewer's hours were also shifted by the difference between the computer's zone and the country's.

When STRIDE loads a project, it checks the `energy_projection` table and logs a warning if the table needs to be rebuilt. To fix it, re-create the project with `stride projects create`.

## For developers

- Database sessions, including dbt's (`dbt/profiles.yml`), run with `TimeZone = 'UTC'`, so results never depend on the machine.
- Never extract fields (`EXTRACT`, `DAYOFWEEK`, `DATE_TRUNC`, ...) from a bare `TIMESTAMPTZ`; the result would depend on the session time zone. Convert first:
  - In SQL, use `timezone(time_zone, timestamp)`.
  - In Python, use `stride.api.utils.local_time_expr`.
- Use `ISODOW` (Monday=1 … Sunday=7) for weekday logic. DuckDB's `DAYOFWEEK` numbers Sunday as 0.
- `tests/test_time_alignment.py` checks these conventions against an independent pandas/zoneinfo reference.

## Related Topics

- {ref}`global-dataset-data-sources` - Where the weather and load shape data come from
- {ref}`weather-year-modeling` - How weather data shape the hourly load
- {ref}`data-api-tutorial` - Querying results from Python
- {ref}`export-results` - Exporting results
