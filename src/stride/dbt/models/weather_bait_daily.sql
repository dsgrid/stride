{{
    config(
        materialized='view'
    )
}}

-- Extract date components and day type from weather BAIT data
SELECT
    geography,
    timestamp,
    value AS bait,
    -- Extract date components for grouping
    EXTRACT(YEAR FROM timestamp) AS weather_year,
    EXTRACT(MONTH FROM timestamp) AS month,
    EXTRACT(DAY FROM timestamp) AS day,
    -- Determine if weekday or weekend (1=Monday, 7=Sunday in DuckDB)
    CASE 
        WHEN DAYOFWEEK(timestamp) IN (6, 7) THEN 'weekend'
        ELSE 'weekday'
    END AS day_type
FROM {{ source('scenario', 'weather_bait') }}
WHERE geography = '{{ var("country") }}'
    AND EXTRACT(YEAR FROM timestamp) = {{ var("weather_year") }}
