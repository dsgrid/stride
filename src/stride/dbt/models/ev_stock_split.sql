-- Split EV stock into BEVs and PHEVs
SELECT
    e.geography
    ,e.model_year
    ,e.ev_stock_total * (1 - p.phev_share) AS bev_stock
    ,e.ev_stock_total * p.phev_share AS phev_stock
FROM {{ table_ref('ev_stock_total') }} e
JOIN {{ table_ref('phev_share_country') }} p
    ON e.geography = p.geography
    AND e.model_year = p.model_year
