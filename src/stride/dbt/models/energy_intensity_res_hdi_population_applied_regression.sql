SELECT
    geography
    ,model_year
    ,sector
    ,CASE
        WHEN regression_type = 'exp'
            THEN EXP(a0 + a1 * (model_year - t0)) * hdi_value * population_value
        WHEN regression_type = 'lin'
            THEN (a0 + a1 * (model_year - t0)) * hdi_value * population_value
    END AS value
FROM {{ table_ref('energy_intensity_res_hdi_population') }} e
