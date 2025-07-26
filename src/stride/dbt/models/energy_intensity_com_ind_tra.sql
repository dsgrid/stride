SELECT *
FROM {{ ref('energy_intensity_parsed') }}
WHERE sector IN ('commercial', 'industrial', 'transportation')
