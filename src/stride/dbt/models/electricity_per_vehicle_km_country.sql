SELECT
    geography
    ,subsector
    ,model_year
    ,value AS wh_per_km
FROM {{ source('scenario', 'electricity_per_vehicle_km_projections') }}
WHERE geography = '{{ var("country") }}' AND model_year IN {{ var("model_years") }}
