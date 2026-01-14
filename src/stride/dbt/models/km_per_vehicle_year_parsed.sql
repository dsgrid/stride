SELECT
    geography
    ,split_part(metric::VARCHAR, '_', 1) AS parameter
    ,split_part(metric::VARCHAR, '_', 2) AS regression_type
    ,value
FROM {{ source('scenario', 'km_per_vehicle_year_regressions') }}
WHERE geography = '{{ var("country") }}'
