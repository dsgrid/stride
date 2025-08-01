SELECT
    e.geography
    ,e.sector
    ,e.a0
    ,e.a1
    ,e.regression_type
    ,e.model_year
    ,e.hdi_value
    ,e.population_value
    ,p.metric
    ,p.timestamp
    ,p.value
FROM {{ table_ref('energy_intensity_res_hdi_population') }} e
JOIN {{ table_ref('load_shapes_res') }} p
    ON e.geography = p.geography AND e.sector = p.sector
