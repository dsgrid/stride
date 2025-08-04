from typing import Any, Sequence
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
    load_shapes: DuckDBPyRelation,
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
    ei_gdp_regression = ei_gdp.select(
        """
        model_year
        ,geography
        ,sector
        ,CASE
            WHEN regression_type = 'exp'
                THEN EXP(a0 + a1) * gdp_value
            WHEN regression_type = 'lin'
                THEN (a0 + a1) * gdp_value
        END AS value
    """
    )

    return load_shapes.join(
        ei_gdp_regression,
        f"""
            {load_shapes.alias}.geography = {ei_gdp_regression.alias}.geography AND
            {load_shapes.alias}.sector = {ei_gdp_regression.alias}.sector
        """,
    ).select(
        f"""
        {load_shapes.alias}.timestamp
        ,{ei_gdp_regression.alias}.model_year
        ,'{scenario}' AS scenario
        ,{ei_gdp_regression.alias}.geography
        ,{ei_gdp_regression.alias}.sector
        ,{load_shapes.alias}.metric
        ,{ei_gdp_regression.alias}.value * {load_shapes.alias}.value AS value
    """
    )


def compute_energy_projection_res(
    con: DuckDBPyConnection,
    ei: DuckDBPyRelation,
    load_shapes: DuckDBPyRelation,
    hdi: DuckDBPyRelation,
    pop: DuckDBPyRelation,
    scenario: str,
) -> DuckDBPyRelation:
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
    ei_hdi_pop_regression = ei.join(hdi_pop, "geography").select(  # noqa: F841
        """
        model_year
        ,geography
        ,sector
        ,CASE
            WHEN regression_type = 'exp' THEN EXP(a0 + a1) * hdi_value * pop_value
            WHEN regression_type = 'lin' THEN (a0 + a1) *  hdi_value * pop_value
        END AS value
    """
    )
    return con.sql(
        f"""
        SELECT
            ls.timestamp
            ,e.model_year
            ,'{scenario}' AS scenario
            ,e.geography
            ,e.sector
            ,ls.metric
            ,ls.value * e.value AS value
        FROM load_shapes ls
        JOIN ei_hdi_pop_regression e
            ON e.geography = ls.geography AND e.sector = ls.sector
        """
    )


def filter_by_com_ind_tra(rel: DuckDBPyRelation) -> DuckDBPyRelation:
    clause = make_is_in_clause(("commercial", "industrial", "transportation"))
    return rel.filter(f"sector in {clause}")


def filter_by_res(rel: DuckDBPyRelation) -> DuckDBPyRelation:
    return rel.filter("sector = 'residential'")


def make_is_in_clause(values: Sequence[Any]) -> str:
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
