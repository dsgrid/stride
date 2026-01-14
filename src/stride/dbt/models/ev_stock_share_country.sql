SELECT
    geography
    ,model_year
    ,value AS ev_stock_share
FROM {{ source('scenario', 'ev_stock_share_projections') }}
WHERE geography = '{{ var("country") }}' AND model_year IN {{ var("model_years") }}
