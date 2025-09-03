PIVOT {{ table_ref('energy_intensity_com_ind_tra') }}
ON parameter IN ('a0', 'a1', 't0')
USING SUM(value)
