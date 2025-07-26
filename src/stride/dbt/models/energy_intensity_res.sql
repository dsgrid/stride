SELECT *
FROM {{ ref('energy_intensity_parsed') }}
WHERE sector = 'residential'
