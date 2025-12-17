{{
    config(
        materialized='view'
    )
}}

WITH load_shapes_base AS (
    -- Get load shapes data (representative days)
    -- This has hourly profiles for representative weekday/weekend days per month
    -- Data structure: month, hour, is_weekday represent typical days, not full year
    SELECT
        geography,
        model_year,
        month,
        hour,
        is_weekday,
        sector,
        metric AS enduse,
        value AS load_shape_value,
        -- Determine day type for joining with temperature multipliers
        CASE 
            WHEN is_weekday THEN 'weekday'
            ELSE 'weekend'
        END AS day_type
    FROM {{ source('scenario', 'load_shapes') }}
    WHERE geography = '{{ var("country") }}'
        AND model_year IN {{ var("model_years") }}
),

enduse_multiplier_mapping AS (
    -- Map end uses to multiplier types (heating, cooling, or other)
    SELECT
        enduse,
        CASE
            -- End uses that respond to heating
            WHEN enduse IN ('heating') THEN 'heating'
            -- End uses that respond to cooling  
            WHEN enduse IN ('cooling') THEN 'cooling'
            -- All other end uses don't adjust with temperature
            ELSE 'other'
        END AS multiplier_type
    FROM (SELECT DISTINCT enduse FROM load_shapes_base)
),

load_shapes_with_multiplier_type AS (
    -- Join load shapes with their multiplier type
    SELECT
        ls.*,
        em.multiplier_type
    FROM load_shapes_base ls
    JOIN enduse_multiplier_mapping em ON ls.enduse = em.enduse
),

-- Expand load shapes to full year by joining with temperature multipliers
-- Temperature multipliers have one row per actual day of the weather year
-- Representative days (month, day_type, hour) get expanded to all matching actual days
load_shapes_expanded_to_full_year AS (
    SELECT
        ls.geography,
        ls.model_year,
        ls.sector,
        ls.enduse,
        ls.multiplier_type,
        -- Create timestamp for this specific hour of this specific day
        -- tm.timestamp is the date (at midnight), add hours to get the hourly timestamp
        tm.timestamp + INTERVAL (ls.hour) HOUR AS timestamp,
        tm.weather_year,
        tm.month,
        tm.day,
        tm.day_type,
        ls.hour,
        ls.load_shape_value,
        -- Select the appropriate multiplier based on end use type
        CASE 
            WHEN ls.multiplier_type = 'heating' THEN tm.heating_multiplier
            WHEN ls.multiplier_type = 'cooling' THEN tm.cooling_multiplier
            ELSE tm.other_multiplier
        END AS multiplier
    FROM load_shapes_with_multiplier_type ls
    JOIN {{ ref('temperature_multipliers') }} tm
        ON ls.geography = tm.geography
        AND ls.month = tm.month
        AND ls.day_type = tm.day_type
),

load_shapes_adjusted AS (
    -- Apply temperature multipliers to load shape values
    SELECT
        geography,
        model_year,
        sector,
        enduse,
        timestamp,
        weather_year,
        load_shape_value,
        multiplier,
        load_shape_value * multiplier AS adjusted_value
    FROM load_shapes_expanded_to_full_year
)

SELECT * FROM load_shapes_adjusted
