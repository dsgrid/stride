-- Calculate total energy consumption for EVs
-- Energy (Wh/year) = stock * km_per_vehicle_year * wh_per_km
WITH bev_energy AS (
    SELECT
        s.geography
        ,s.model_year
        ,'bev' AS ev_type
        ,s.bev_stock * k.km_per_vehicle_year * e.wh_per_km AS wh_per_year
    FROM {{ table_ref('ev_stock_split') }} s
    JOIN {{ table_ref('km_per_vehicle_year_applied') }} k
        ON s.geography = k.geography
        AND s.model_year = k.model_year
    JOIN {{ table_ref('electricity_per_vehicle_km_country') }} e
        ON s.geography = e.geography
        AND s.model_year = e.model_year
        AND e.subsector = 'bev'
),

phev_energy AS (
    SELECT
        s.geography
        ,s.model_year
        ,'phev' AS ev_type
        ,s.phev_stock * k.km_per_vehicle_year * e.wh_per_km AS wh_per_year
    FROM {{ table_ref('ev_stock_split') }} s
    JOIN {{ table_ref('km_per_vehicle_year_applied') }} k
        ON s.geography = k.geography
        AND s.model_year = k.model_year
    JOIN {{ table_ref('electricity_per_vehicle_km_country') }} e
        ON s.geography = e.geography
        AND s.model_year = e.model_year
        AND e.subsector = 'phev'
)

SELECT * FROM bev_energy
UNION ALL
SELECT * FROM phev_energy
