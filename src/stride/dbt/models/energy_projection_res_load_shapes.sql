SELECT
    ls.timestamp
    ,e.model_year
    ,e.geography
    ,e.sector
    ,ls.metric
    ,ls.value * e.value AS value
FROM {{ table_ref('load_shapes_res') }} ls
JOIN {{ table_ref('energy_intensity_res_hdi_population_applied_regression') }} e
    ON e.geography = ls.geography AND e.sector = ls.sector
