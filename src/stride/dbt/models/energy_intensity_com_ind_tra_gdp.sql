SELECT
    e.sector
    ,e.a0
    ,e.a1
    ,e.t0
    ,e.regression_type
    ,g.geography
    ,g.model_year
    ,g.value AS gdp_value
FROM {{ table_ref('energy_intensity_com_ind_tra_pivoted') }} e
JOIN {{ table_ref('gdp_country') }} g
    ON e.geography = g.geography
