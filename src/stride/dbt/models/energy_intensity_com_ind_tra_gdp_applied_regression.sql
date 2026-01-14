SELECT
    geography
    ,model_year
    ,sector
    ,subsector
    ,CASE
        WHEN regression_type = 'exp'
            THEN EXP(a0 + a1 * (model_year - t0)) * gdp_value
        WHEN regression_type = 'lin'
            THEN (a0 + a1 * (model_year - t0)) * gdp_value
    END AS value
FROM {{ table_ref('energy_intensity_com_ind_tra_gdp') }} e
