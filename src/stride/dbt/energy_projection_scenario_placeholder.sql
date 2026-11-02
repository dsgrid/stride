-- timestamp is an absolute instant (TIMESTAMPTZ). time_zone is the geography's standard time
-- zone; use timezone(time_zone, timestamp) to get local standard time.
WITH tmp AS (
    SELECT * FROM {{ table_ref('energy_projection_com_ind_tra_load_shapes') }}
    UNION ALL
    SELECT * FROM {{ table_ref('energy_projection_res_load_shapes') }}
),
time_zones AS (
    SELECT DISTINCT geography, time_zone FROM {{ ref('weather_bait_daily') }}
)
SELECT tmp.*, time_zones.time_zone, '{{ var("scenario") }}' AS scenario
FROM tmp
LEFT JOIN time_zones ON tmp.geography = time_zones.geography
