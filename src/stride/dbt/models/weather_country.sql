SELECT
    geography
    ,timestamp
    ,temperature
    ,humidity
FROM {{ source('scenario', 'weather') }}
WHERE geography = '{{ var("country") }}'
