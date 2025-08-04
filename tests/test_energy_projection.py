from typing import Sequence
from uuid import uuid4

from duckdb import DuckDBPyConnection, DuckDBPyRelation
from pandas.testing import assert_frame_equal

from stride import Project


def test_energy_projection(default_project: Project) -> None:
    """Validate the energy projection computed through dbt with an independent computation
    directly through DuckDB.
    """
    project = default_project
    actual = project.get_energy_projection()
    actual_df = actual.sort(*actual.columns).to_df()
    expected_baseline = compute_energy_projection(project.con, "baseline", project.config.country)
    expected_alt = compute_energy_projection(project.con, "alternate_gdp", project.config.country)
    expected = expected_baseline.union(expected_alt)
    expected_df = expected.select(*actual.columns).sort(*actual.columns).to_df()
    assert_frame_equal(actual_df, expected_df)


def compute_energy_projection(
    con: DuckDBPyConnection,
    scenario: str,
    country: str,
) -> DuckDBPyRelation:
    energy_intensity_parsed = make_energy_intensity_parsed(con, scenario, country)
    profiles = con.table("dsgrid_data.baseline__load_shapes").filter(f"geography = '{country}'")
    rel_cit = compute_energy_projection_com_ind_tra(
        filter_by_com_ind_tra(energy_intensity_parsed),
        filter_by_com_ind_tra(profiles),
        con.table(f"dsgrid_data.{scenario}__gdp__1_0_0").filter(f"geography = '{country}'"),
        scenario,
    )
    rel_res = compute_energy_projection_res(
        con,
        filter_by_res(energy_intensity_parsed),
        filter_by_res(profiles),
        con.table(f"dsgrid_data.{scenario}__hdi__1_0_0").filter(f"geography = '{country}'"),
        con.table(f"dsgrid_data.{scenario}__population__1_0_0").filter(f"geography = '{country}'"),
        scenario,
    )
    return rel_cit.union(rel_res)


def compute_energy_projection_com_ind_tra(
    ei: DuckDBPyRelation,
    profiles: DuckDBPyRelation,
    gdp: DuckDBPyRelation,
    scenario: str,
) -> DuckDBPyRelation:
    ei_gdp = ei.join(gdp, "geography").select(
        f"""
        {ei.alias}.*
        ,{gdp.alias}.model_year
        ,{gdp.alias}.value AS gdp_value
    """
    )
    ei_gdp_profiles = ei_gdp.join(
        profiles,
        f"""
            {ei_gdp.alias}.geography = {profiles.alias}.geography AND
            {ei_gdp.alias}.sector = {profiles.alias}.sector
        """,
    ).select(
        f"""
        {profiles.alias}.timestamp
        ,{ei_gdp.alias}.model_year
        ,{ei_gdp.alias}.geography
        ,{profiles.alias}.metric
        ,{ei_gdp.alias}.sector
        ,{ei_gdp.alias}.regression_type
        ,{ei_gdp.alias}.a0
        ,{ei_gdp.alias}.a1
        ,{ei_gdp.alias}.gdp_value
        ,{profiles.alias}.value
    """
    )
    return ei_gdp_profiles.select(
        f"""
        timestamp
        ,model_year
        ,'{scenario}' AS scenario
        ,geography
        ,sector
        ,metric
        ,CASE
            WHEN regression_type = 'exp'
                THEN EXP(a0 + a1) * gdp_value * value
            WHEN regression_type = 'lin'
                THEN (a0 + a1) * gdp_value * value
        END AS value
    """
    )


def compute_energy_projection_res(
    con: DuckDBPyConnection,
    ei: DuckDBPyRelation,
    profiles: DuckDBPyRelation,
    hdi: DuckDBPyRelation,
    pop: DuckDBPyRelation,
    scenario: str,
) -> DuckDBPyRelation:
    profiles.set_alias("res_profiles")
    hdi_pop = hdi.join(
        pop,
        f"""
        {hdi.alias}.geography = {pop.alias}.geography AND
        {hdi.alias}.model_year = {pop.alias}.model_year
    """,
    ).select(
        f"""
        {hdi.alias}.geography
        ,{hdi.alias}.model_year
        ,{hdi.alias}.value AS hdi_value
        ,{pop.alias}.value AS pop_value
    """
    )
    ei_hdi_pop = ei.join(hdi_pop, "geography")  # noqa: F841
    ei_hdi_pop_profiles = con.sql(
        """
        SELECT
            p.timestamp
            ,e.model_year
            ,e.geography
            ,e.sector
            ,p.metric
            ,e.regression_type
            ,e.a0
            ,e.a1
            ,e.hdi_value
            ,e.pop_value
            ,p.value
        FROM ei_hdi_pop e
        JOIN profiles p
            ON e.geography = p.geography AND e.sector = p.sector
        """
    )
    return ei_hdi_pop_profiles.select(
        f"""
            timestamp
            ,model_year
            ,'{scenario}' AS scenario
            ,geography
            ,sector
            ,metric
            ,CASE
                WHEN regression_type = 'exp' THEN EXP(a0 + a1) * hdi_value * pop_value * value
                WHEN regression_type = 'lin' THEN (a0 + a1) *  hdi_value * pop_value * value
            END AS value
        """
    )


def filter_by_com_ind_tra(rel: DuckDBPyRelation) -> DuckDBPyRelation:
    clause = make_is_in_clause(("commercial", "industrial", "transportation"))
    return rel.filter(f"sector in {clause}")


def filter_by_res(rel: DuckDBPyRelation) -> DuckDBPyRelation:
    return rel.filter("sector = 'residential'")


def make_is_in_clause(values: Sequence) -> str:
    if isinstance(values[0], str):
        vals = (f"'{x}'" for x in values)
        return "(" + ",".join(vals) + ")"
    return ",".join((str(x) for x in values))


def make_tmp_view_name() -> str:
    return str(uuid4()).replace("-", "")


def make_energy_intensity_parsed(
    con: DuckDBPyConnection, scenario: str, country: str
) -> DuckDBPyRelation:
    rel = (
        con.table(f"dsgrid_data.{scenario}__energy_intensity__1_0_0")
        .filter(f"geography = '{country}'")
        .select(
            """
       geography
       ,sector
       ,SPLIT_PART(metric, '_', 2) AS parameter
       ,SPLIT_PART(metric, '_', 3) AS regression_type
       ,value
    """
        )
    )
    pivoted = pivot_energy_intensity(con, rel)
    return pivoted


def pivot_energy_intensity(con: DuckDBPyConnection, rel: DuckDBPyRelation) -> DuckDBPyRelation:
    return con.sql(
        """
        PIVOT
            (SELECT * FROM rel)
        ON parameter IN ('a0', 'a1')
        USING SUM(value)
    """
    )
