{{
    config(
        materialized='view'
    )
}}

-- Pivot weather data from long format (metric column) to wide format and extract date components
--
-- Time conventions:
-- - timestamp is a TIMESTAMPTZ instant: the start of the local-standard-time day
--   (e.g., 2018-01-01 00:00 in Etc/GMT-1 for Germany, which is 2017-12-31 23:00 UTC).
-- - time_zone is the geography's standard time zone (no daylight saving time).
-- - local_date is the naive local-standard-time start of the day. All date labels
--   (month, day, day_type) are derived from it. Never extract fields from a bare
--   TIMESTAMPTZ: the result would depend on the session time zone.
WITH weather AS (
    SELECT
        geography,
        timestamp,
        time_zone,
        timezone(time_zone, timestamp) AS local_date,
        CAST(weather_year AS INTEGER) AS weather_year,
        metric,
        value
    FROM {{ source('scenario', 'weather_bait') }}
    WHERE geography = '{{ var("country") }}'
        AND CAST(weather_year AS INTEGER) = {{ var("weather_year") }}
)

SELECT
    geography,
    timestamp,
    time_zone,
    local_date,
    MAX(CASE WHEN metric = 'Temperature' THEN value END) AS temperature,
    MAX(CASE WHEN metric = 'Solar_Radiation' THEN value END) AS solar_radiation,
    MAX(CASE WHEN metric = 'Wind_Speed' THEN value END) AS wind_speed,
    MAX(CASE WHEN metric = 'Dew_Point' THEN value END) AS dew_point,
    MAX(CASE WHEN metric = 'Humidity' THEN value END) AS humidity,
    MAX(CASE WHEN metric = 'BAIT' THEN value END) AS bait,
    weather_year,
    EXTRACT(MONTH FROM local_date) AS month,
    EXTRACT(DAY FROM local_date) AS day,
    -- ISO day of week: 1=Monday ... 6=Saturday, 7=Sunday
    CASE
        WHEN ISODOW(local_date) IN (6, 7) THEN 'weekend'
        ELSE 'weekday'
    END AS day_type
FROM weather
GROUP BY geography, timestamp, time_zone, local_date, weather_year
