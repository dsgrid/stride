SELECT
    geography
    ,timestamp
    ,model_year
    ,sector
    ,CASE
        WHEN regression_type = 'exp'
            THEN EXP(a0 + a1) * hdi_value * population_value * value
        WHEN regression_type = 'lin'
            THEN (a0 + a1) * hdi_value * population_value * value
    END AS value
FROM {{ ref('energy_intensity_res_hdi_population_load_shapes') }} e
