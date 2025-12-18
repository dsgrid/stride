PIVOT {{ table_ref('vehicle_per_capita_parsed') }}
ON parameter IN ('a0', 'a1', 't0')
USING SUM(value)
GROUP BY geography, regression_type
