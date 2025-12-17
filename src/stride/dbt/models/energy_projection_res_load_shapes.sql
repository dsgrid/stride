WITH load_shapes_filtered AS (
    -- Get temperature-adjusted load shapes for residential sector
    SELECT
        geography,
        model_year,
        sector,
        enduse,
        timestamp,
        adjusted_value
    FROM {{ ref('load_shapes_expanded') }}
    WHERE sector = 'residential'
),

load_shapes_annual_totals AS (
    -- Calculate annual energy totals from load shapes (for scaling)
    -- Sum across all enduses since STRIDE annual energy is at sector level
    SELECT
        geography,
        model_year,
        sector,
        SUM(adjusted_value) AS load_shape_annual_total
    FROM load_shapes_filtered
    GROUP BY geography, model_year, sector
),

stride_annual_energy AS (
    -- Get STRIDE annual energy projections (from energy intensity calculations)
    SELECT
        geography,
        model_year,
        sector,
        value AS stride_annual_total
    FROM {{ table_ref('energy_intensity_res_hdi_population_applied_regression') }}
),

scaling_factors AS (
    -- Compute scaling factor: STRIDE annual / load shape annual
    -- This scales the temperature-adjusted load shapes to match STRIDE totals
    -- Same scaling factor applies to all enduses within a sector
    SELECT
        ls.geography,
        ls.model_year,
        ls.sector,
        CASE 
            WHEN ls.load_shape_annual_total > 0 
            THEN stride.stride_annual_total / ls.load_shape_annual_total
            ELSE 1.0
        END AS scaling_factor
    FROM load_shapes_annual_totals ls
    JOIN stride_annual_energy stride
        ON ls.geography = stride.geography
        AND ls.model_year = stride.model_year
        AND ls.sector = stride.sector
)

-- Apply scaling factors to create final hourly energy projections
SELECT
    ls.timestamp,
    ls.model_year,
    ls.geography,
    ls.sector,
    ls.enduse AS metric,
    ls.adjusted_value * sf.scaling_factor AS value
FROM load_shapes_filtered ls
JOIN scaling_factors sf
    ON ls.geography = sf.geography
    AND ls.model_year = sf.model_year
    AND ls.sector = sf.sector
