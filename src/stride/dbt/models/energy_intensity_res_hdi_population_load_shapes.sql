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
FROM {{ ref('energy_intensity_res_hdi_population') }} e
JOIN {{ ref('load_shapes_res') }} p ON e.geography = p.geography
