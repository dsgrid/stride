{{
    config(
        materialized='view'
    )
}}

-- Calculate heating and cooling degree days from BAIT temperature data
SELECT
    *,
    -- HDD: heating degree days when temperature is below heating threshold
    GREATEST(0, {{ var('heating_threshold', 18.0) }} - bait) AS hdd,
    -- CDD: cooling degree days when temperature is above cooling threshold
    GREATEST(0, bait - {{ var('cooling_threshold', 18.0) }}) AS cdd
FROM {{ ref('weather_bait_daily') }}
