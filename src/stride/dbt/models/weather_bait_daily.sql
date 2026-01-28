{{
    config(
        materialized='view'
    )
}}

-- Pivot weather data from long format (metric column) to wide format and extract date components
SELECT
    geography,
    timestamp,
    MAX(CASE WHEN metric = 'Temperature' THEN value END) AS temperature,
    MAX(CASE WHEN metric = 'Solar_Radiation' THEN value END) AS solar_radiation,
    MAX(CASE WHEN metric = 'Wind_Speed' THEN value END) AS wind_speed,
    MAX(CASE WHEN metric = 'Dew_Point' THEN value END) AS dew_point,
    MAX(CASE WHEN metric = 'Humidity' THEN value END) AS humidity,
    MAX(CASE WHEN metric = 'BAIT' THEN value END) AS bait,
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
GROUP BY geography, timestamp
