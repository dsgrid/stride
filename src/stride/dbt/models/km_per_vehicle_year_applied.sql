-- Calculate km per vehicle per year using regression, expanded to model years
SELECT
    k.geography
    ,p.model_year
    ,CASE
        WHEN k.regression_type = 'exp'
            THEN EXP(k.a0 + k.a1 * (p.model_year - k.t0))
        WHEN k.regression_type = 'lin'
            THEN (k.a0 + k.a1 * (p.model_year - k.t0))
    END AS km_per_vehicle_year
FROM {{ table_ref('km_per_vehicle_year_pivoted') }} k
JOIN {{ table_ref('population_country') }} p
    ON k.geography = p.geography
