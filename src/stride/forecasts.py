from typing import Sequence
from uuid import uuid4

from duckdb import DuckDBPyConnection, DuckDBPyRelation


def compute_energy_projection(
    con: DuckDBPyConnection,
    ei_name: str,
    hdi_table: str,
    gdp_table: str,
    pop_table: str,
    profiles_name: str,
    geo_column: str,
    geo_value: str,
    table_name: str = "energy_projection",
) -> None:
    """Compute the energy intensity for each sector in the table and add it to the database."""
    rel_cit = compute_energy_projection_com_ind_tra(
        con,
        ei_name,
        profiles_name,
        geo_column,
        geo_value,
        gdp_table,
    )
    rel_r = compute_energy_projection_res(
        con,
        ei_name,
        profiles_name,
        geo_column,
        geo_value,
        hdi_table,
        pop_table,
    )
    rel_cit.union(rel_r).to_table(table_name)


def compute_energy_projection_com_ind_tra(
    con: DuckDBPyConnection,
    ei_name: str,
    profiles_name: str,
    geo_column: str,
    geo_value: str,
    gdp_name: str,
) -> DuckDBPyRelation:
    """Compute energy projection for commercial, industrial, and transportation sectors."""
    r_gdp = con.table(gdp_name).filter(f"{geo_column} = '{geo_value}'")
    filtered_ei = filter_by_com_ind_tra(con.table(ei_name)).filter(f"{geo_column} = '{geo_value}'")
    filtered_profiles = filter_by_com_ind_tra(con.table(profiles_name)).filter(
        f"{geo_column} = '{geo_value}'"
    )
    ei_piv = pivot_energy_intensity(con, filtered_ei)
    ei_gdp = ei_piv.join(r_gdp, geo_column).select(
        f"{ei_piv.alias}.*, {r_gdp.alias}.year, {r_gdp.alias}.value"
    )
    ei_gdp_profiles = ei_gdp.join(
        filtered_profiles,
        f"""
            {ei_gdp.alias}.{geo_column} = {filtered_profiles.alias}.{geo_column} AND
            {ei_gdp.alias}.sector = {filtered_profiles.alias}.sector
        """,
    ).select(f"""
        {ei_gdp.alias}.{geo_column}
        ,{ei_gdp.alias}.year
        ,{ei_gdp.alias}.sector
        ,{ei_gdp.alias}.model_type
        ,{ei_gdp.alias}.intercept
        ,{ei_gdp.alias}.slope
        ,{ei_gdp.alias}.value AS gdp_value
        ,{filtered_profiles.alias}.hour
        ,{filtered_profiles.alias}.value
    """)
    # TODO: refactor with CaseExpression?
    return ei_gdp_profiles.select(f"""
        hour
        ,year
        ,{geo_column}
        ,sector
        ,CASE
            WHEN model_type = 'exp'
                THEN EXP(intercept + slope) * gdp_value * value
            WHEN model_type = 'lin'
                THEN (intercept + slope) * gdp_value * value
        END AS value
    """)


def compute_energy_projection_res(
    con: DuckDBPyConnection,
    ei_name: str,
    profiles_name: str,
    geo_column: str,
    geo_value: str,
    hdi_name: str,
    pop_name: str,
) -> DuckDBPyRelation:
    """Compute energy projection for the residential sector."""
    rel_hdi = con.table(hdi_name).filter(f"{geo_column} = '{geo_value}'")
    rel_pop = con.table(pop_name).filter(f"{geo_column} = '{geo_value}'")
    filtered_ei = filter_by_res(con.table(ei_name)).filter(f"{geo_column} = '{geo_value}'")
    filtered_profiles = filter_by_res(con.table(profiles_name)).filter(
        f"{geo_column} = '{geo_value}'"
    )
    ei_piv = pivot_energy_intensity(con, filtered_ei)
    ei_hdi = (
        ei_piv.join(rel_hdi, geo_column)
        .join(rel_pop, geo_column)
        .select(f"""
                {ei_piv.alias}.*,
                {rel_hdi.alias}.year,
                {rel_hdi.alias}.value AS hdi_value,
            """)
    )
    ei_hdi_pop = ei_hdi.join(
        rel_pop,
        f"""
            {ei_hdi.alias}.{geo_column} = {rel_pop.alias}.{geo_column} AND
            {ei_hdi.alias}.year = {rel_pop.alias}.year
    """,
    ).select(f"""
        {ei_hdi.alias}.*,
        {rel_pop.alias}.value AS pop_value,
    """)
    ei_hdi_pop_profiles = ei_hdi_pop.join(
        filtered_profiles,
        f"""
                {ei_hdi_pop.alias}.{geo_column} = {filtered_profiles.alias}.{geo_column} AND
                {ei_hdi_pop.alias}.sector = {filtered_profiles.alias}.sector
            """,
    ).select(f"""
         {ei_hdi_pop.alias}.{geo_column}
        ,{ei_hdi_pop.alias}.year
        ,{ei_hdi_pop.alias}.sector
        ,{ei_hdi_pop.alias}.model_type
        ,{ei_hdi_pop.alias}.intercept
        ,{ei_hdi_pop.alias}.slope
        ,{ei_hdi_pop.alias}.hdi_value
        ,{ei_hdi_pop.alias}.pop_value
        ,{filtered_profiles.alias}.hour
        ,{filtered_profiles.alias}.value
    """)
    return ei_hdi_pop_profiles.select(f"""
            hour
            ,year
            ,{geo_column}
            ,sector
            ,CASE
                WHEN model_type = 'exp' THEN EXP(intercept + slope) * hdi_value * pop_value * value
                WHEN model_type = 'lin' THEN (intercept + slope) *  hdi_value * pop_value * value
            END AS value
        """)


def filter_by_com_ind_tra(rel: DuckDBPyRelation) -> DuckDBPyRelation:
    # TODO: Can the Expression API work here?
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


def pivot_energy_intensity(con: DuckDBPyConnection, rel: DuckDBPyRelation) -> DuckDBPyRelation:
    return con.sql(f"""
        PIVOT
            (SELECT * EXCLUDE unit FROM {rel.alias})
        ON parameter
        USING SUM(value)
    """)
