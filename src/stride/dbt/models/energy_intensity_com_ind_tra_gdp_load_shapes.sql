SELECT
    e.geography
    ,e.model_year
    ,e.sector
    ,e.regression_type
    ,e.a0
    ,e.a1
    ,e.value as gdp_value
    ,p.timestamp
    ,p.value
FROM {{ table_ref('energy_intensity_com_ind_tra_gdp') }} e
JOIN {{ table_ref('load_shapes_com_ind_tra') }} p
    ON e.geography = p.geography AND e.sector = p.sector
