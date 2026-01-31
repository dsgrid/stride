{{
    config(
        materialized='view'
    )
}}

-- Calculate temperature adjustment multipliers for each day
-- These multipliers adjust load shapes based on daily temperature variations

WITH max_degree_days AS (
    -- Calculate maximum degree days for each group
    -- Used to smooth shoulder month transitions by setting a minimum threshold
    SELECT
        geography,
        weather_year,
        month,
        day_type,
        MAX(hdd) AS max_hdd,
        MAX(cdd) AS max_cdd
    FROM {{ ref('weather_degree_days') }}
    GROUP BY geography, weather_year, month, day_type
),

adjusted_degree_days AS (
    -- Adjust low degree days in shoulder months to smooth transitions
    -- In months with some heating/cooling, apply a minimum threshold (max / factor)
    -- This affects both zero values and small non-zero values below the threshold
    -- Only applies if enable_shoulder_month_smoothing is True
    SELECT
        dd.geography,
        dd.timestamp,
        dd.weather_year,
        dd.month,
        dd.day,
        dd.day_type,
        dd.bait,
        dd.hdd AS original_hdd,
        dd.cdd AS original_cdd,
        gs.num_days,
        gs.total_hdd,
        gs.total_cdd,
        mdd.max_hdd,
        mdd.max_cdd,
        -- Adjusted HDD: apply minimum threshold (max_hdd / factor) in shoulder months (if enabled)
        -- Default factor is defined in stride.models.DEFAULT_SHOULDER_MONTH_SMOOTHING_FACTOR
        CASE
            WHEN {{ var('enable_shoulder_month_smoothing', true) }}
                 AND gs.total_hdd > 0 AND mdd.max_hdd IS NOT NULL
                 AND dd.hdd < (mdd.max_hdd / {{ var('shoulder_month_smoothing_factor', 10.0) }})
            THEN mdd.max_hdd / {{ var('shoulder_month_smoothing_factor', 10.0) }}
            ELSE dd.hdd
        END AS adjusted_hdd,
        -- Adjusted CDD: apply minimum threshold (max_cdd / factor) in shoulder months (if enabled)
        -- Default factor is defined in stride.models.DEFAULT_SHOULDER_MONTH_SMOOTHING_FACTOR
        CASE
            WHEN {{ var('enable_shoulder_month_smoothing', true) }}
                 AND gs.total_cdd > 0 AND mdd.max_cdd IS NOT NULL
                 AND dd.cdd < (mdd.max_cdd / {{ var('shoulder_month_smoothing_factor', 10.0) }})
            THEN mdd.max_cdd / {{ var('shoulder_month_smoothing_factor', 10.0) }}
            ELSE dd.cdd
        END AS adjusted_cdd
    FROM {{ ref('weather_degree_days') }} dd
    JOIN {{ ref('weather_degree_days_grouped') }} gs
        ON dd.weather_year = gs.weather_year
        AND dd.month = gs.month
        AND dd.day_type = gs.day_type
        AND dd.geography = gs.geography
    LEFT JOIN max_degree_days mdd
        ON dd.weather_year = mdd.weather_year
        AND dd.month = mdd.month
        AND dd.day_type = mdd.day_type
        AND dd.geography = mdd.geography
),

adjusted_totals AS (
    -- Recalculate totals with adjusted values
    SELECT
        geography,
        weather_year,
        month,
        day_type,
        SUM(adjusted_hdd) AS adjusted_total_hdd,
        SUM(adjusted_cdd) AS adjusted_total_cdd
    FROM adjusted_degree_days
    GROUP BY geography, weather_year, month, day_type
)

-- Calculate multipliers using adjusted degree days
SELECT
    ad.geography,
    ad.timestamp,
    ad.weather_year,
    ad.month,
    ad.day,
    ad.day_type,
    ad.bait,
    ad.original_hdd AS hdd,
    ad.original_cdd AS cdd,
    ad.adjusted_hdd,
    ad.adjusted_cdd,
    ad.num_days,
    ad.total_hdd,
    ad.total_cdd,
    -- Heating multiplier: normalize adjusted HDD within the group
    -- If total_hdd is zero, no heating occurs in this period, so multiplier is 1.0
    CASE
        WHEN ad.total_hdd = 0 OR ad.total_hdd IS NULL THEN 1.0
        ELSE (ad.adjusted_hdd / at.adjusted_total_hdd) * ad.num_days
    END AS heating_multiplier,
    -- Cooling multiplier: normalize adjusted CDD within the group
    -- If total_cdd is zero, no cooling occurs in this period, so multiplier is 1.0
    CASE
        WHEN ad.total_cdd = 0 OR ad.total_cdd IS NULL THEN 1.0
        ELSE (ad.adjusted_cdd / at.adjusted_total_cdd) * ad.num_days
    END AS cooling_multiplier,
    -- Other multiplier is always 1.0 (no temperature adjustment for non-HVAC loads)
    1.0 AS other_multiplier
FROM adjusted_degree_days ad
JOIN adjusted_totals at
    ON ad.weather_year = at.weather_year
    AND ad.month = at.month
    AND ad.day_type = at.day_type
    AND ad.geography = at.geography
