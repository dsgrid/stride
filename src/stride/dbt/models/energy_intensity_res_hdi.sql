SELECT
    e.sector
    ,e.a0
    ,e.a1
    ,e.t0
    ,e.regression_type
    ,h.geography
    ,h.model_year
    ,h.value AS hdi_value
FROM {{ table_ref('energy_intensity_res_pivoted') }} e
JOIN {{ table_ref('hdi_country') }} h
    ON e.geography = h.geography
