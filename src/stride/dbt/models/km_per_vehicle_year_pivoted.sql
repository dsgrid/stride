PIVOT {{ table_ref('km_per_vehicle_year_parsed') }}
ON parameter IN ('a0', 'a1', 't0')
USING SUM(value)
GROUP BY geography, regression_type
