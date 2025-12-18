SELECT
    geography
    ,model_year
    ,value AS phev_share
FROM {{ source('scenario', 'phev_share_projections') }}
WHERE geography = '{{ var("country") }}' AND model_year IN {{ var("model_years") }}
