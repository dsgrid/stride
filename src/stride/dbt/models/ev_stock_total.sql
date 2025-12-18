-- Calculate total EV stock by multiplying vehicle stock by EV share
SELECT
    v.geography
    ,v.model_year
    ,v.total_vehicles * e.ev_stock_share AS ev_stock_total
FROM {{ table_ref('vehicle_stock_total') }} v
JOIN {{ table_ref('ev_stock_share_country') }} e
    ON v.geography = e.geography
    AND v.model_year = e.model_year
