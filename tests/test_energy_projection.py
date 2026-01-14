from duckdb import DuckDBPyConnection, DuckDBPyRelation
from pandas.testing import assert_frame_equal

from stride import Project

# Conversion factor: 1 TJ = 1000/3.6 MWh
TJ_TO_MWH = 1000 / 3.6


def test_energy_projection(default_project: Project) -> None:
    """Validate the energy projection computed through dbt with an independent computation
    directly through DuckDB.

    The energy projection is computed by:
    1. Computing annual energy from energy intensity regressions with GDP/HDI/population
    2. Expanding load shapes to full year with temperature adjustments
    3. Computing scaling factors to match annual totals
    4. Applying scaling factors to hourly load shapes

    Note: This test only validates scenarios that use the standard energy intensity
    calculation. Scenarios with use_ev_projection=True (like ev_projection) use
    different EV-based calculations and are excluded from this test.
    """
    project = default_project
    # Filter to scenarios that use standard energy intensity calculation (not EV projection)
    scenarios_to_test = ["baseline", "alternate_gdp"]
    actual = project.get_energy_projection().filter(
        f"scenario IN ({','.join(repr(s) for s in scenarios_to_test)})"
    )
    actual_df = actual.sort(*actual.columns).to_df()

    country = project.config.country
    weather_year = project.config.weather_year

    expected_baseline = compute_energy_projection(project.con, "baseline", country, weather_year)
    expected_alt = compute_energy_projection(project.con, "alternate_gdp", country, weather_year)
    expected = expected_baseline.union(expected_alt)
    expected_df = expected.select(*actual.columns).sort(*actual.columns).to_df()

    assert_frame_equal(actual_df, expected_df)


def test_energy_projection_by_scenario(default_project: Project) -> None:
    project = default_project
    expected = project.get_energy_projection().filter("scenario = 'baseline'").to_df()
    actual = project.get_energy_projection(scenario="baseline").to_df()
    assert_frame_equal(actual[expected.columns], expected)


def test_energy_projection_ev(default_project: Project) -> None:
    """Validate the EV projection computed through dbt with an independent computation.

    When use_ev_projection=True, the Transportation/Road sector uses EV-based
    energy calculation instead of energy intensity regression. The EV projection
    calculates energy from:
    - Vehicle stock (from vehicle per capita regression * population)
    - EV share of vehicle stock
    - BEV/PHEV split
    - km per vehicle per year (from regression)
    - Electricity consumption per km (Wh/km)
    """
    project = default_project
    scenario = "ev_projection"

    actual = project.get_energy_projection().filter(f"scenario = '{scenario}'")
    actual_df = actual.sort(*actual.columns).to_df()

    country = project.config.country
    weather_year = project.config.weather_year

    expected = compute_energy_projection_with_ev(project.con, scenario, country, weather_year)
    expected_df = expected.select(*actual.columns).sort(*actual.columns).to_df()

    assert_frame_equal(actual_df, expected_df)


def compute_energy_projection(
    con: DuckDBPyConnection,
    scenario: str,
    country: str,
    weather_year: int,
) -> DuckDBPyRelation:
    """Compute energy projection independently of dbt models."""
    model_years = get_model_years(con, scenario)
    rel_cit = compute_energy_projection_com_ind_tra(
        con, scenario, country, model_years, weather_year
    )
    rel_res = compute_energy_projection_res(con, scenario, country, model_years, weather_year)

    return rel_cit.union(rel_res)


def compute_energy_projection_with_ev(
    con: DuckDBPyConnection,
    scenario: str,
    country: str,
    weather_year: int,
) -> DuckDBPyRelation:
    """Compute energy projection with EV-based Transportation/Road calculation.

    This is used when use_ev_projection=True. The Transportation/Road sector
    uses EV stock and efficiency data instead of energy intensity regression.
    """
    model_years = get_model_years(con, scenario)

    # Commercial, Industrial, and non-Road Transportation use standard calculation
    rel_cit = compute_energy_projection_com_ind_tra_with_ev(
        con, scenario, country, model_years, weather_year
    )
    # Residential uses standard calculation
    rel_res = compute_energy_projection_res(con, scenario, country, model_years, weather_year)

    return rel_cit.union(rel_res)


def compute_energy_projection_com_ind_tra_with_ev(
    con: DuckDBPyConnection,
    scenario: str,
    country: str,
    model_years: list[int],
    weather_year: int,
) -> DuckDBPyRelation:
    """Compute CIT energy projection with EV-based Transportation/Road.

    For use_ev_projection=True:
    - Commercial and Industrial use standard energy intensity regression
    - Transportation/Road uses EV stock * km/vehicle * Wh/km calculation
    """
    model_years_tuple = tuple(model_years)

    # Get energy intensity with regression coefficients (excluding Transportation/Road)
    energy_intensity = make_energy_intensity_pivoted(con, scenario, country)
    ei_com_ind_tra = energy_intensity.filter(
        "sector IN ('Commercial', 'Industrial', 'Transportation')"
    )

    # Join with GDP
    gdp = con.sql(
        f"""
        SELECT geography, model_year, value AS gdp_value
        FROM dsgrid_data.{scenario}__gdp__1_0_0
        WHERE geography = '{country}'
    """
    )

    ei_gdp = ei_com_ind_tra.join(gdp, "geography")

    # Standard energy intensity calculation (excludes Transportation/Road when EV is used)
    stride_annual_energy_base = ei_gdp.select(  # noqa F841
        f"""
        geography
        ,model_year
        ,sector
        ,subsector
        ,CASE
            WHEN regression_type = 'exp'
                THEN EXP(a0 + a1 * (model_year - t0)) * gdp_value
            WHEN regression_type = 'lin'
                THEN (a0 + a1 * (model_year - t0)) * gdp_value
        END * {TJ_TO_MWH} AS stride_annual_total
    """
    )

    # Exclude Transportation/Road from base (will be replaced by EV calculation)
    stride_annual_energy_non_ev = con.sql(  # noqa: F841
        """
        SELECT * FROM stride_annual_energy_base
        WHERE NOT (sector = 'Transportation' AND subsector = 'Road')
    """
    )

    # Calculate EV annual energy
    ev_annual_energy = compute_ev_annual_energy(con, scenario, country, model_years_tuple)  # noqa F841

    # Combine: non-EV sectors + EV Transportation/Road
    stride_annual_energy = con.sql(  # noqa: F841
        """
        SELECT geography, model_year, sector, subsector, stride_annual_total
        FROM stride_annual_energy_non_ev
        UNION ALL
        SELECT geography, model_year, sector, subsector, stride_annual_total
        FROM ev_annual_energy
    """
    )

    # Get temperature-adjusted load shapes expanded to full year
    load_shapes = get_load_shapes_expanded(con, scenario, country, model_years, weather_year)
    ls_cit = load_shapes.filter("sector IN ('Commercial', 'Industrial', 'Transportation')")  # noqa F841

    # Calculate annual totals from load shapes (sum across all end uses)
    ls_annual_totals = con.sql(  # noqa F841
        """
        SELECT geography, model_year, sector, SUM(adjusted_value) AS load_shape_annual_total
        FROM ls_cit
        GROUP BY geography, model_year, sector
    """
    )

    # Compute scaling factors (aggregate subsectors since load shapes are at sector level)
    stride_by_sector = con.sql(  # noqa F841
        """
        SELECT geography, model_year, sector, SUM(stride_annual_total) AS stride_annual_total
        FROM stride_annual_energy
        GROUP BY geography, model_year, sector
    """
    )

    scaling_factors = con.sql(  # noqa F841
        """
        SELECT
            ls.geography
            ,ls.model_year
            ,ls.sector
            ,CASE
                WHEN ls.load_shape_annual_total > 0
                THEN stride.stride_annual_total / ls.load_shape_annual_total
                ELSE 1.0
            END AS scaling_factor
        FROM ls_annual_totals ls
        JOIN stride_by_sector stride
            ON ls.geography = stride.geography
            AND ls.model_year = stride.model_year
            AND ls.sector = stride.sector
    """
    )

    # Apply scaling factors to get final hourly projections
    return con.sql(
        f"""
        SELECT
            ls.timestamp
            ,ls.model_year
            ,'{scenario}' AS scenario
            ,ls.geography
            ,ls.sector
            ,ls.enduse AS metric
            ,ls.adjusted_value * sf.scaling_factor AS value
        FROM ls_cit ls
        JOIN scaling_factors sf
            ON ls.geography = sf.geography
            AND ls.model_year = sf.model_year
            AND ls.sector = sf.sector
    """
    )


def compute_ev_annual_energy(
    con: DuckDBPyConnection,
    scenario: str,
    country: str,
    model_years_tuple: tuple[int, ...],
) -> DuckDBPyRelation:
    """Compute EV annual energy in MWh for Transportation/Road sector.

    EV energy = stock * km_per_vehicle_year * wh_per_km, converted to MWh.
    """
    # 1. Parse and pivot vehicle per capita regressions
    vehicle_per_capita_parsed = con.sql(  # noqa: F841
        f"""
        SELECT
            geography
            ,split_part(metric::VARCHAR, '_', 1) AS parameter
            ,split_part(metric::VARCHAR, '_', 2) AS regression_type
            ,value
        FROM dsgrid_data.{scenario}__vehicle_per_capita_regressions__1_0_0
        WHERE geography = '{country}'
    """
    )

    vehicle_per_capita_pivoted = con.sql(  # noqa: F841
        """
        PIVOT vehicle_per_capita_parsed
        ON parameter IN ('a0', 'a1', 't0')
        USING SUM(value)
        GROUP BY geography, regression_type
    """
    )

    # 2. Join with population
    population = con.sql(  # noqa F841
        f"""
        SELECT geography, model_year, value AS population_value
        FROM dsgrid_data.{scenario}__population__1_0_0
        WHERE geography = '{country}' AND model_year IN {model_years_tuple}
    """
    )

    vehicle_per_capita_pop = con.sql(  # noqa: F841
        """
        SELECT v.*, p.model_year, p.population_value
        FROM vehicle_per_capita_pivoted v
        JOIN population p ON v.geography = p.geography
    """
    )

    # 3. Calculate total vehicle stock
    vehicle_stock_total = con.sql(  # noqa: F841
        """
        SELECT
            geography
            ,model_year
            ,CASE
                WHEN regression_type = 'exp'
                    THEN EXP(a0 + a1 * (model_year - t0)) * population_value
                WHEN regression_type = 'lin'
                    THEN (a0 + a1 * (model_year - t0)) * population_value
            END AS total_vehicles
        FROM vehicle_per_capita_pop
    """
    )

    # 4. Get EV stock share
    ev_stock_share = con.sql(  # noqa F841
        f"""
        SELECT geography, model_year, value AS ev_stock_share
        FROM dsgrid_data.{scenario}__ev_stock_share_projections__1_0_0
        WHERE geography = '{country}' AND model_year IN {model_years_tuple}
    """
    )

    # 5. Calculate total EV stock
    ev_stock_total = con.sql(  # noqa: F841
        """
        SELECT
            v.geography
            ,v.model_year
            ,v.total_vehicles * e.ev_stock_share AS ev_stock_total
        FROM vehicle_stock_total v
        JOIN ev_stock_share e
            ON v.geography = e.geography
            AND v.model_year = e.model_year
    """
    )

    # 6. Get PHEV share and split into BEV/PHEV
    phev_share = con.sql(  # noqa F841
        f"""
        SELECT geography, model_year, value AS phev_share
        FROM dsgrid_data.{scenario}__phev_share_projections__1_0_0
        WHERE geography = '{country}' AND model_year IN {model_years_tuple}
    """
    )

    ev_stock_split = con.sql(  # noqa: F841
        """
        SELECT
            e.geography
            ,e.model_year
            ,e.ev_stock_total * (1 - p.phev_share) AS bev_stock
            ,e.ev_stock_total * p.phev_share AS phev_stock
        FROM ev_stock_total e
        JOIN phev_share p
            ON e.geography = p.geography
            AND e.model_year = p.model_year
    """
    )

    # 7. Parse and pivot km per vehicle year regressions
    km_per_vehicle_parsed = con.sql(  # noqa: F841
        f"""
        SELECT
            geography
            ,split_part(metric::VARCHAR, '_', 1) AS parameter
            ,split_part(metric::VARCHAR, '_', 2) AS regression_type
            ,value
        FROM dsgrid_data.{scenario}__km_per_vehicle_year_regressions__1_0_0
        WHERE geography = '{country}'
    """
    )

    km_per_vehicle_pivoted = con.sql(  # noqa: F841
        """
        PIVOT km_per_vehicle_parsed
        ON parameter IN ('a0', 'a1', 't0')
        USING SUM(value)
        GROUP BY geography, regression_type
    """
    )

    # 8. Calculate km per vehicle per year (use population table for model years)
    km_per_vehicle_applied = con.sql(  # noqa: F841
        """
        SELECT
            k.geography
            ,p.model_year
            ,CASE
                WHEN k.regression_type = 'exp'
                    THEN EXP(k.a0 + k.a1 * (p.model_year - k.t0))
                WHEN k.regression_type = 'lin'
                    THEN (k.a0 + k.a1 * (p.model_year - k.t0))
            END AS km_per_vehicle_year
        FROM km_per_vehicle_pivoted k
        JOIN population p ON k.geography = p.geography
    """
    )

    # 9. Get electricity per km for BEV and PHEV
    electricity_per_km = con.sql(  # noqa F841
        f"""
        SELECT geography, subsector, model_year, value AS wh_per_km
        FROM dsgrid_data.{scenario}__electricity_per_vehicle_km_projections__1_0_0
        WHERE geography = '{country}' AND model_year IN {model_years_tuple}
    """
    )

    # 10. Calculate BEV and PHEV energy (Wh/year)
    bev_energy = con.sql(  # noqa: F841
        """
        SELECT
            s.geography
            ,s.model_year
            ,'bev' AS ev_type
            ,s.bev_stock * k.km_per_vehicle_year * e.wh_per_km AS wh_per_year
        FROM ev_stock_split s
        JOIN km_per_vehicle_applied k
            ON s.geography = k.geography
            AND s.model_year = k.model_year
        JOIN electricity_per_km e
            ON s.geography = e.geography
            AND s.model_year = e.model_year
            AND e.subsector = 'bev'
    """
    )

    phev_energy = con.sql(  # noqa: F841
        """
        SELECT
            s.geography
            ,s.model_year
            ,'phev' AS ev_type
            ,s.phev_stock * k.km_per_vehicle_year * e.wh_per_km AS wh_per_year
        FROM ev_stock_split s
        JOIN km_per_vehicle_applied k
            ON s.geography = k.geography
            AND s.model_year = k.model_year
        JOIN electricity_per_km e
            ON s.geography = e.geography
            AND s.model_year = e.model_year
            AND e.subsector = 'phev'
    """
    )

    ev_energy_by_type = con.sql(  # noqa: F841
        """
        SELECT * FROM bev_energy
        UNION ALL
        SELECT * FROM phev_energy
    """
    )

    # 11. Sum and convert from Wh to TJ, then to MWh
    # 1 TJ = 277,777,777.778 Wh, so Wh / 277777777.778 = TJ
    # Then TJ * TJ_TO_MWH = MWh
    wh_to_tj = 277777777.778
    return con.sql(
        f"""
        SELECT
            geography
            ,model_year
            ,'Transportation' AS sector
            ,'Road' AS subsector
            ,SUM(wh_per_year) / {wh_to_tj} * {TJ_TO_MWH} AS stride_annual_total
        FROM ev_energy_by_type
        GROUP BY geography, model_year
    """
    )


def get_model_years(con: DuckDBPyConnection, scenario: str) -> list[int]:
    """Get the model years from the GDP table for a scenario."""
    table_name = f"dsgrid_data.{scenario}__gdp__1_0_0"
    years = con.sql(f"SELECT DISTINCT model_year FROM {table_name} ORDER BY model_year").fetchall()
    return [y[0] for y in years]


def compute_energy_projection_com_ind_tra(
    con: DuckDBPyConnection,
    scenario: str,
    country: str,
    model_years: list[int],
    weather_year: int,
) -> DuckDBPyRelation:
    """Compute energy projection for commercial, industrial, transportation sectors."""
    # Get energy intensity with regression coefficients
    energy_intensity = make_energy_intensity_pivoted(con, scenario, country)
    ei_com_ind_tra = energy_intensity.filter(
        "sector IN ('Commercial', 'Industrial', 'Transportation')"
    )

    # Join with GDP
    gdp = con.sql(
        f"""
        SELECT geography, model_year, value AS gdp_value
        FROM dsgrid_data.{scenario}__gdp__1_0_0
        WHERE geography = '{country}'
    """
    )

    ei_gdp = ei_com_ind_tra.join(gdp, "geography")

    # Apply regression to get annual energy in TJ, then convert to MWh
    stride_annual_energy = ei_gdp.select(  # noqa F841
        f"""
        geography
        ,model_year
        ,sector
        ,subsector
        ,CASE
            WHEN regression_type = 'exp'
                THEN EXP(a0 + a1 * (model_year - t0)) * gdp_value
            WHEN regression_type = 'lin'
                THEN (a0 + a1 * (model_year - t0)) * gdp_value
        END * {TJ_TO_MWH} AS stride_annual_total
    """
    )

    # Get temperature-adjusted load shapes expanded to full year
    load_shapes = get_load_shapes_expanded(con, scenario, country, model_years, weather_year)
    ls_cit = load_shapes.filter("sector IN ('Commercial', 'Industrial', 'Transportation')")  # noqa F841

    # Calculate annual totals from load shapes (sum across all end uses)
    ls_annual_totals = con.sql(  # noqa F841
        """
        SELECT geography, model_year, sector, SUM(adjusted_value) AS load_shape_annual_total
        FROM ls_cit
        GROUP BY geography, model_year, sector
    """
    )

    # Compute scaling factors (aggregate subsectors since load shapes are at sector level)
    stride_by_sector = con.sql(  # noqa F841
        """
        SELECT geography, model_year, sector, SUM(stride_annual_total) AS stride_annual_total
        FROM stride_annual_energy
        GROUP BY geography, model_year, sector
    """
    )

    scaling_factors = con.sql(  # noqa F841
        """
        SELECT
            ls.geography
            ,ls.model_year
            ,ls.sector
            ,CASE
                WHEN ls.load_shape_annual_total > 0
                THEN stride.stride_annual_total / ls.load_shape_annual_total
                ELSE 1.0
            END AS scaling_factor
        FROM ls_annual_totals ls
        JOIN stride_by_sector stride
            ON ls.geography = stride.geography
            AND ls.model_year = stride.model_year
            AND ls.sector = stride.sector
    """
    )

    # Apply scaling factors to get final hourly projections
    return con.sql(  # noqa F841
        f"""
        SELECT
            ls.timestamp
            ,ls.model_year
            ,'{scenario}' AS scenario
            ,ls.geography
            ,ls.sector
            ,ls.enduse AS metric
            ,ls.adjusted_value * sf.scaling_factor AS value
        FROM ls_cit ls
        JOIN scaling_factors sf
            ON ls.geography = sf.geography
            AND ls.model_year = sf.model_year
            AND ls.sector = sf.sector
    """
    )


def compute_energy_projection_res(
    con: DuckDBPyConnection,
    scenario: str,
    country: str,
    model_years: list[int],
    weather_year: int,
) -> DuckDBPyRelation:
    """Compute energy projection for residential sector."""
    # Get energy intensity with regression coefficients
    energy_intensity = make_energy_intensity_pivoted(con, scenario, country)
    ei_res = energy_intensity.filter("sector = 'Residential'")

    # Join with HDI
    hdi = con.sql(  # noqa F841
        f"""
        SELECT geography, model_year, value AS hdi_value
        FROM dsgrid_data.{scenario}__hdi__1_0_0
        WHERE geography = '{country}'
    """
    )
    ei_hdi = ei_res.join(hdi, "geography")  # noqa F841

    # Join with population
    pop = con.sql(  # noqa F841
        f"""
        SELECT geography, model_year, value AS pop_value
        FROM dsgrid_data.{scenario}__population__1_0_0
        WHERE geography = '{country}'
    """
    )
    ei_hdi_pop = con.sql(
        """
        SELECT
            e.geography
            ,p.model_year
            ,e.sector
            ,e.subsector
            ,e.a0
            ,e.a1
            ,e.t0
            ,e.regression_type
            ,e.hdi_value
            ,p.pop_value
        FROM ei_hdi e
        JOIN pop p ON e.geography = p.geography AND e.model_year = p.model_year
    """
    )

    # Apply regression to get annual energy in TJ, then convert to MWh
    stride_annual_energy = ei_hdi_pop.select(  # noqa: F841
        f"""
        geography
        ,model_year
        ,sector
        ,subsector
        ,CASE
            WHEN regression_type = 'exp'
                THEN EXP(a0 + a1 * (model_year - t0)) * hdi_value * pop_value
            WHEN regression_type = 'lin'
                THEN (a0 + a1 * (model_year - t0)) * hdi_value * pop_value
        END * {TJ_TO_MWH} AS stride_annual_total
    """
    )

    # Get temperature-adjusted load shapes expanded to full year
    load_shapes = get_load_shapes_expanded(con, scenario, country, model_years, weather_year)
    ls_res = load_shapes.filter("sector = 'Residential'")  # noqa: F841

    # Calculate annual totals from load shapes (sum across all enduses)
    ls_annual_totals = con.sql(  # noqa: F841
        """
        SELECT geography, model_year, sector, SUM(adjusted_value) AS load_shape_annual_total
        FROM ls_res
        GROUP BY geography, model_year, sector
    """
    )

    # Compute scaling factors (aggregate subsectors since load shapes are at sector level)
    stride_by_sector = con.sql(  # noqa: F841
        """
        SELECT geography, model_year, sector, SUM(stride_annual_total) AS stride_annual_total
        FROM stride_annual_energy
        GROUP BY geography, model_year, sector
    """
    )

    scaling_factors = con.sql(  # noqa: F841
        """
        SELECT
            ls.geography
            ,ls.model_year
            ,ls.sector
            ,CASE
                WHEN ls.load_shape_annual_total > 0
                THEN stride.stride_annual_total / ls.load_shape_annual_total
                ELSE 1.0
            END AS scaling_factor
        FROM ls_annual_totals ls
        JOIN stride_by_sector stride
            ON ls.geography = stride.geography
            AND ls.model_year = stride.model_year
            AND ls.sector = stride.sector
    """
    )

    # Apply scaling factors to get final hourly projections
    return con.sql(
        f"""
        SELECT
            ls.timestamp
            ,ls.model_year
            ,'{scenario}' AS scenario
            ,ls.geography
            ,ls.sector
            ,ls.enduse AS metric
            ,ls.adjusted_value * sf.scaling_factor AS value
        FROM ls_res ls
        JOIN scaling_factors sf
            ON ls.geography = sf.geography
            AND ls.model_year = sf.model_year
            AND ls.sector = sf.sector
    """
    )


def get_load_shapes_expanded(
    con: DuckDBPyConnection,
    scenario: str,
    country: str,
    model_years: list[int],
    weather_year: int,
) -> DuckDBPyRelation:
    """Get load shapes expanded to full year with temperature adjustments applied.

    This replicates the load_shapes_expanded dbt model.
    """
    model_years_tuple = tuple(model_years)

    # Get temperature multipliers (which include the full year expansion)
    # First, compute temperature multipliers
    temp_multipliers = compute_temperature_multipliers(con, scenario, country, weather_year)  # noqa F841

    # Get base load shapes and map sector names
    load_shapes_base = con.sql(  # noqa: F841
        f"""
        SELECT
            geography
            ,model_year
            ,month
            ,hour
            ,is_weekday
            ,CASE
                WHEN sector = 'Industry' THEN 'Industrial'
                WHEN sector = 'Transport' THEN 'Transportation'
                WHEN sector = 'Service' THEN 'Commercial'
                ELSE sector
            END AS sector
            ,metric AS enduse
            ,value AS load_shape_value
            ,CASE
                WHEN is_weekday THEN 'weekday'
                ELSE 'weekend'
            END AS day_type
        FROM dsgrid_data.{scenario}__load_shapes__1_0_0
        WHERE geography = '{country}'
            AND model_year IN {model_years_tuple}
    """
    )

    # Map enduses to multiplier types
    enduse_mapping = con.sql(  # noqa: F841
        """
        SELECT
            enduse
            ,CASE
                WHEN enduse IN ('heating') THEN 'heating'
                WHEN enduse IN ('cooling') THEN 'cooling'
                ELSE 'other'
            END AS multiplier_type
        FROM (SELECT DISTINCT enduse FROM load_shapes_base)
    """
    )

    ls_with_multiplier_type = con.sql(  # noqa: F841
        """
        SELECT ls.*, em.multiplier_type
        FROM load_shapes_base ls
        JOIN enduse_mapping em ON ls.enduse = em.enduse
    """
    )

    # Expand to full year by joining with temperature multipliers
    load_shapes_expanded = con.sql(  # noqa: F841
        """
        SELECT
            ls.geography
            ,ls.model_year
            ,ls.sector
            ,ls.enduse
            ,ls.multiplier_type
            ,tm.timestamp + INTERVAL (ls.hour) HOUR AS timestamp
            ,tm.weather_year
            ,tm.month AS actual_month
            ,tm.day
            ,tm.day_type AS actual_day_type
            ,ls.hour
            ,ls.load_shape_value
            ,CASE
                WHEN ls.multiplier_type = 'heating' THEN tm.heating_multiplier
                WHEN ls.multiplier_type = 'cooling' THEN tm.cooling_multiplier
                ELSE tm.other_multiplier
            END AS multiplier
        FROM ls_with_multiplier_type ls
        JOIN temp_multipliers tm
            ON ls.geography = tm.geography
            AND ls.month = tm.month
            AND ls.day_type = tm.day_type
    """
    )

    # Apply temperature adjustments
    return con.sql(
        """
        SELECT
            geography
            ,model_year
            ,sector
            ,enduse
            ,timestamp
            ,weather_year
            ,load_shape_value
            ,multiplier
            ,load_shape_value * multiplier AS adjusted_value
        FROM load_shapes_expanded
    """
    )


def compute_temperature_multipliers(
    con: DuckDBPyConnection, scenario: str, country: str, weather_year: int
) -> DuckDBPyRelation:
    """Compute temperature multipliers that expand representative days to full year.

    This replicates the temperature_multipliers dbt model.
    """
    # Get daily BAIT data (matching weather_bait_daily.sql)
    weather_bait_daily = con.sql(  # noqa: F841
        f"""
        SELECT
            geography
            ,timestamp
            ,value AS bait
            ,EXTRACT(YEAR FROM timestamp) AS weather_year
            ,EXTRACT(MONTH FROM timestamp) AS month
            ,EXTRACT(DAY FROM timestamp) AS day
            ,CASE
                WHEN DAYOFWEEK(timestamp) IN (6, 7) THEN 'weekend'
                ELSE 'weekday'
            END AS day_type
        FROM dsgrid_data.{scenario}__weather_bait__1_0_0
        WHERE geography = '{country}'
            AND EXTRACT(YEAR FROM timestamp) = {weather_year}
    """
    )

    # Compute degree days (matching weather_degree_days.sql)
    weather_degree_days = con.sql(  # noqa: F841
        """
        SELECT
            *
            ,GREATEST(0, 18.0 - bait) AS hdd
            ,GREATEST(0, bait - 18.0) AS cdd
        FROM weather_bait_daily
    """
    )

    # Group by month and day type to get totals (matching weather_degree_days_grouped.sql)
    weather_grouped = con.sql(  # noqa: F841
        """
        SELECT
            geography
            ,weather_year
            ,month
            ,day_type
            ,COUNT(*) AS num_days
            ,SUM(hdd) AS total_hdd
            ,SUM(cdd) AS total_cdd
        FROM weather_degree_days
        GROUP BY geography, weather_year, month, day_type
    """
    )

    # Compute multipliers (matching temperature_multipliers.sql)
    return con.sql(
        """
        SELECT
            dd.geography
            ,dd.timestamp
            ,dd.weather_year
            ,dd.month
            ,dd.day
            ,dd.day_type
            ,dd.bait
            ,dd.hdd
            ,dd.cdd
            ,gs.num_days
            ,gs.total_hdd
            ,gs.total_cdd
            ,CASE
                WHEN gs.total_hdd = 0 OR gs.total_hdd IS NULL THEN 1.0
                ELSE (dd.hdd / gs.total_hdd) * gs.num_days
            END AS heating_multiplier
            ,CASE
                WHEN gs.total_cdd = 0 OR gs.total_cdd IS NULL THEN 1.0
                ELSE (dd.cdd / gs.total_cdd) * gs.num_days
            END AS cooling_multiplier
            ,1.0 AS other_multiplier
        FROM weather_degree_days dd
        JOIN weather_grouped gs
            ON dd.geography = gs.geography
            AND dd.weather_year = gs.weather_year
            AND dd.month = gs.month
            AND dd.day_type = gs.day_type
    """
    )


def make_energy_intensity_pivoted(
    con: DuckDBPyConnection, scenario: str, country: str
) -> DuckDBPyRelation:
    """Parse and pivot energy intensity data to get regression coefficients."""
    # Parse energy intensity
    parsed = con.sql(  # noqa F841
        f"""
        SELECT
            geography
            ,sector
            ,subsector
            ,SPLIT_PART(metric, '_', 2) AS parameter
            ,SPLIT_PART(metric, '_', 3) AS regression_type
            ,value
        FROM dsgrid_data.{scenario}__energy_intensity__1_0_0
        WHERE geography = '{country}'
    """
    )

    # Pivot to get a0, a1, t0 as columns
    return con.sql(
        """
        PIVOT (SELECT * FROM parsed)
        ON parameter IN ('a0', 'a1', 't0')
        USING SUM(value)
        GROUP BY geography, sector, subsector, regression_type
    """
    )
