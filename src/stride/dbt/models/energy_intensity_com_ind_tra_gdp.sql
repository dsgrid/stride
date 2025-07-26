SELECT
    e.sector
    ,e.a0
    ,e.a1
    ,e.regression_type
    ,g.geography
    ,g.model_year
    ,g.value
FROM {{ ref('energy_intensity_com_ind_tra_pivoted') }} e
CROSS JOIN {{ ref('gdp_country') }} g
