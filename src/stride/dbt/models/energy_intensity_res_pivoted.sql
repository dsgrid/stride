PIVOT {{ table_ref('energy_intensity_res') }}
ON parameter IN ('a0', 'a1')
USING SUM(value)
