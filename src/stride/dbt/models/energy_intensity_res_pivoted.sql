PIVOT {{ table_ref('energy_intensity_res') }}
ON parameter IN ('a0', 'a1', 't0')
USING SUM(value)
GROUP BY geography, sector, subsector, regression_type
