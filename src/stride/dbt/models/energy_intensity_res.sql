SELECT *
FROM {{ table_ref('energy_intensity_parsed') }}
WHERE sector = 'residential'
