SELECT *
FROM {{ source('scenario', 'load_shapes') }}
WHERE sector = 'residential'
