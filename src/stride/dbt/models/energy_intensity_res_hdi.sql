SELECT
    e.sector
    ,e.a0
    ,e.a1
    ,e.regression_type
    ,h.geography
    ,h.model_year
    ,h.value AS hdi_value
FROM {{ ref('energy_intensity_res_pivoted') }} e
CROSS JOIN {{ ref('hdi_country') }} h
