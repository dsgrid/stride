{% set scenario = var('scenario', 'active_scenario') %}

SELECT *
FROM {{ source(scenario, 'load_shapes') }}
WHERE sector In ('commercial', 'industrial', 'transportation')
