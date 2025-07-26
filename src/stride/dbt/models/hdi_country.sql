{% set scenario = var('scenario', 'active_scenario') %}

SELECT
    geography
    ,model_year
    ,value
FROM {{ source(scenario, 'hdi') }}
WHERE geography = '{{ var("country") }}' AND model_year in {{ var("model_years") }}
