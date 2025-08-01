{{ config(materialized='table') }}

WITH tmp AS (
    SELECT * FROM {{ ref('energy_projection_com_ind_tra') }}
    UNION ALL
    SELECT * FROM {{ ref('energy_projection_res') }}
) SELECT *, '{{ var("scenario") }}' AS scenario FROM tmp
