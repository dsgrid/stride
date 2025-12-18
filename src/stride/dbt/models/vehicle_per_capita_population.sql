SELECT
    v.geography
    ,v.a0
    ,v.a1
    ,v.t0
    ,v.regression_type
    ,p.model_year
    ,p.value AS population_value
FROM {{ table_ref('vehicle_per_capita_pivoted') }} v
JOIN {{ table_ref('population_country') }} p
    ON v.geography = p.geography
