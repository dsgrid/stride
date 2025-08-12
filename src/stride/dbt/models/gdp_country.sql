SELECT
    geography
    ,model_year
    ,value
FROM {{ source('scenario', 'gdp') }}
WHERE geography = '{{ var("country") }}' AND model_year in {{ var("model_years") }}
