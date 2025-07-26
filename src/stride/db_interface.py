def make_stride_table_name(scenario_name: str, base_table_name: str) -> str:
    """Make a full table name that includes the schema and scenario."""
    return f"stride.{scenario_name}__{base_table_name}"


def make_dsgrid_data_table_name(
    scenario_name: str, base_table_name: str, version: str = "1.0.0"
) -> str:
    """Make a full table name that includes the schema, scenario, and version."""
    ver = version.replace(".", "_")
    return f"dsgrid_data.{scenario_name}__{base_table_name}__{ver}"
