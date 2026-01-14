-- Calculate total vehicle stock based on vehicles per capita regression
SELECT
    geography
    ,model_year
    ,CASE
        WHEN regression_type = 'exp'
            THEN EXP(a0 + a1 * (model_year - t0)) * population_value
        WHEN regression_type = 'lin'
            THEN (a0 + a1 * (model_year - t0)) * population_value
    END AS total_vehicles
FROM {{ table_ref('vehicle_per_capita_population') }}
