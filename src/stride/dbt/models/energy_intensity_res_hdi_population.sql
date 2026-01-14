SELECT
    e.geography
    ,e.sector
    ,e.subsector
    ,e.a0
    ,e.a1
    ,e.t0
    ,e.regression_type
    ,e.model_year
    ,e.hdi_value
    ,p.value AS population_value
FROM {{ table_ref('energy_intensity_res_hdi') }} e
JOIN {{ table_ref('population_country') }} p ON e.geography = p.geography AND e.model_year = p.model_year
