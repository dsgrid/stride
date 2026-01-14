WITH load_shapes_filtered AS (
    -- Get temperature-adjusted load shapes for commercial, industrial, and transportation sectors
    SELECT
        geography,
        model_year,
        sector,
        enduse,
        timestamp,
        adjusted_value
    FROM {{ ref('load_shapes_expanded') }}
    WHERE sector IN ('Commercial', 'Industrial', 'Transportation')
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

stride_annual_energy_base AS (
    -- Get STRIDE annual energy projections (from energy intensity calculations)
    -- Convert from TJ to MWh (1 TJ = 277.777777778 MWh)
    SELECT
        geography,
        model_year,
        sector,
        subsector,
        value * 277.777777778 AS stride_annual_total
    FROM {{ table_ref('energy_intensity_com_ind_tra_gdp_applied_regression') }}
),

ev_annual_energy AS (
    -- Get EV-based annual energy projections if use_ev_projection is enabled
    -- Convert from TJ to MWh (1 TJ = 277.777777778 MWh)
    {% if var("use_ev_projection", False) %}
    SELECT
        geography,
        model_year,
        sector,
        subsector,
        value * 277.777777778 AS stride_annual_total
    FROM {{ table_ref('ev_annual_energy_tj') }}
    {% else %}
    -- Return empty result if EV projection is not enabled
    SELECT
        NULL AS geography,
        NULL AS model_year,
        NULL AS sector,
        NULL AS subsector,
        NULL AS stride_annual_total
    WHERE FALSE
    {% endif %}
),

stride_annual_energy AS (
    -- Combine base energy intensity projections with optional EV projections
    -- If use_ev_projection is true, replace Transportation + Road with EV-based calculation
    SELECT
        geography,
        model_year,
        sector,
        subsector,
        stride_annual_total
    FROM stride_annual_energy_base
    WHERE NOT (sector = 'Transportation' AND subsector = 'Road' AND {{ var("use_ev_projection", False) }})
    
    UNION ALL
    
    SELECT
        geography,
        model_year,
        sector,
        subsector,
        stride_annual_total
    FROM ev_annual_energy
),

scaling_factors AS (
    -- Compute scaling factor: STRIDE annual / load shape annual
    -- This scales the temperature-adjusted load shapes to match STRIDE totals
    -- Same scaling factor applies to all enduses within a sector
    -- Note: Load shapes are at sector level, so we aggregate subsectors
    SELECT
        ls.geography,
        ls.model_year,
        ls.sector,
        CASE 
            WHEN ls.load_shape_annual_total > 0 
            THEN SUM(stride.stride_annual_total) / ls.load_shape_annual_total
            ELSE 1.0
        END AS scaling_factor
    FROM load_shapes_annual_totals ls
    JOIN stride_annual_energy stride
        ON ls.geography = stride.geography
        AND ls.model_year = stride.model_year
        AND ls.sector = stride.sector
    GROUP BY ls.geography, ls.model_year, ls.sector, ls.load_shape_annual_total
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
