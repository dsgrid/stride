{{
    config(
        materialized='view'
    )
}}

-- Aggregate degree days by geography, weather_year, month, and day_type
-- This groups representative days within each month
SELECT
    geography,
    weather_year,
    month,
    day_type,
    COUNT(*) AS num_days,
    SUM(hdd) AS total_hdd,
    SUM(cdd) AS total_cdd
FROM {{ ref('weather_degree_days') }}
GROUP BY geography, weather_year, month, day_type
