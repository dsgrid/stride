{{ config(materialized='table') }}

WITH tmp AS (
    SELECT * FROM {{ ref('energy_projection_com_ind_tra_load_shapes') }}
    UNION ALL
    SELECT * FROM {{ ref('energy_projection_res_load_shapes') }}
) SELECT *, '{{ var("scenario") }}' AS scenario FROM tmp
