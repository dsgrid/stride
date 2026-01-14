-- Sum EV energy across types and convert from Wh to TJ
-- 1 TJ = 277,777,777.778 Wh
SELECT
    geography
    ,model_year
    ,'Transportation' AS sector
    ,'Road' AS subsector
    ,SUM(wh_per_year) / 277777777.778 AS value
FROM {{ table_ref('ev_energy_by_type') }}
GROUP BY geography, model_year
