SELECT
    geography
    ,sector
    ,split_part(metric, '_', 2) AS parameter
    ,split_part(metric, '_', 3) AS regression_type
    ,value
FROM {{ source('scenario', 'energy_intensity') }}
WHERE geography = '{{ var("country") }}'
