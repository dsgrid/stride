{{
    config(
        materialized='view'
    )
}}

-- Calculate temperature adjustment multipliers for each day
-- These multipliers adjust load shapes based on daily temperature variations
SELECT
    dd.geography,
    dd.timestamp,
    dd.weather_year,
    dd.month,
    dd.day,
    dd.day_type,
    dd.bait,
    dd.hdd,
    dd.cdd,
    gs.num_days,
    gs.total_hdd,
    gs.total_cdd,
    -- Heating multiplier: normalize HDD within the group (weather_year, month, day_type)
    -- If total_hdd is zero, no heating occurs in this period, so multiplier is 1.0
    CASE
        WHEN gs.total_hdd = 0 OR gs.total_hdd IS NULL THEN 1.0
        ELSE (dd.hdd / gs.total_hdd) * gs.num_days
    END AS heating_multiplier,
    -- Cooling multiplier: normalize CDD within the group
    -- If total_cdd is zero, no cooling occurs in this period, so multiplier is 1.0
    CASE
        WHEN gs.total_cdd = 0 OR gs.total_cdd IS NULL THEN 1.0
        ELSE (dd.cdd / gs.total_cdd) * gs.num_days
    END AS cooling_multiplier,
    -- Other multiplier is always 1.0 (no temperature adjustment for non-HVAC loads)
    1.0 AS other_multiplier
FROM {{ ref('weather_degree_days') }} dd
JOIN {{ ref('weather_degree_days_grouped') }} gs
    ON dd.weather_year = gs.weather_year
    AND dd.month = gs.month
    AND dd.day_type = gs.day_type
    AND dd.geography = gs.geography
