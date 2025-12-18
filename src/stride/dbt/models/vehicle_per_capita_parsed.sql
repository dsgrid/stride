SELECT
    geography
    ,split_part(metric::VARCHAR, '_', 1) AS parameter
    ,split_part(metric::VARCHAR, '_', 2) AS regression_type
    ,value
FROM {{ source('scenario', 'vehicle_per_capita_regressions') }}
WHERE geography = '{{ var("country") }}'
