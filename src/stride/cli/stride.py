import sys
from pathlib import Path
from typing import Any, Callable

import rich_click as click
from chronify.exceptions import ChronifyExceptionBase
from chronify.loggers import setup_logging
from dsgrid.exceptions import DSGBaseException
from dsgrid.cli.common import path_callback
from loguru import logger

from stride import Project
from stride.models import CalculatedTableOverride


LOGURU_LEVELS = ["TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"]


@click.group("stride")
@click.option(
    "-c",
    "--console-level",
    default="INFO",
    type=click.Choice(LOGURU_LEVELS),
    show_default=True,
    help="Console log level",
)
@click.option(
    "-f",
    "--file-level",
    default="INFO",
    type=click.Choice(LOGURU_LEVELS),
    show_default=True,
    help="Console log level",
)
@click.option(
    "-r",
    "--reraise-exceptions",
    is_flag=True,
    default=False,
    show_default=True,
    help="Re-raise all stride exceptions. Useful for debugging errors.",
)
@click.pass_context
def cli(ctx: click.Context, console_level: str, file_level: str, reraise_exceptions: bool) -> None:
    """Stride comands"""


@click.group()
def projects() -> None:
    """Project commands"""


_create_epilog = """
Examples:\n
$ stride projects create my_project.json5\n
"""


@click.command(name="create", epilog=_create_epilog)
@click.argument("config_file", type=click.Path(exists=True), callback=path_callback)
@click.option(
    "-d",
    "--directory",
    default=Path(),
    show_default=True,
    help="Base directory for the project",
    type=click.Path(),
    callback=path_callback,
)
@click.option(
    "--overwrite",
    default=False,
    show_default=True,
    is_flag=True,
    help="Overwrite the output directory if it exists.",
)
@click.pass_context
def create_project(ctx: click.Context, config_file: Path, directory: Path, overwrite: bool) -> Any:
    """Create a Stride project."""
    setup_logging(
        filename="stride.log",
        console_level=ctx.find_root().params["console_level"],
        file_level=ctx.find_root().params["console_level"],
        mode="a",
    )
    res = handle_stride_exception(
        ctx, Project.create, config_file, base_dir=directory, overwrite=overwrite
    )
    if res[1] != 0:
        ctx.exit(res[1])


@click.group()
def datasets() -> None:
    """Dataset commands"""


@click.command(name="list")
def list_datasets() -> None:
    """List the datasets available in any project."""
    names = Project.list_datasets()
    print(" ".join(names))


@click.command(name="show")
@click.argument("project-path", type=click.Path(exists=True), callback=path_callback)
@click.argument("dataset-id", type=str)
@click.option(
    "-s", "--scenario", type=str, default="baseline", show_default=True, help="Project scenario"
)
@click.option(
    "-l",
    "--limit",
    type=int,
    default=20,
    show_default=True,
    help="Max number of rows in the table to show.",
)
@click.pass_context
def show_dataset(
    ctx: click.Context, project_path: Path, scenario: str, dataset_id: str, limit: int
) -> None:
    """List the datasets stored in the project."""
    project = safe_get_project_from_context(ctx, project_path, read_only=True)
    project.show_dataset(dataset_id, scenario=scenario, limit=limit)


@click.group()
def scenarios() -> None:
    """Scenario commands"""


@click.command(name="list")
@click.argument("project-path", type=click.Path(exists=True), callback=path_callback)
@click.pass_context
def list_scenarios(ctx: click.Context, project_path: Path) -> None:
    """List the scenarios stored in the project."""
    project = safe_get_project_from_context(ctx, project_path, read_only=True)
    scenarios = project.list_scenario_names()
    print(f"Scenarios in project with project_id={project.config.project_id}:")
    for scenario in scenarios:
        print(f"  {scenario}")


@click.group()
def calculated_tables() -> None:
    """Calculated table commands"""


@click.command(name="view")
@click.argument("project-path", type=click.Path(exists=True), callback=path_callback)
@click.option(
    "--host",
    default="127.0.0.1",
    show_default=True,
    help="Host to run the UI server on",
)
@click.option(
    "--port",
    default=8050,
    show_default=True,
    help="Port to run the UI server on",
    type=int,
)
@click.option(
    "--debug",
    is_flag=True,
    default=False,
    show_default=True,
    help="Run in debug mode",
)
@click.pass_context
def view(ctx: click.Context, project_path: Path, host: str, port: int, debug: bool) -> None:
    """Start the STRIDE dashboard UI for the specified project."""
    from stride.ui.app import create_app
    from stride.api import APIClient

    project = safe_get_project_from_context(ctx, project_path)

    data_handler = APIClient(project=project)

    app = create_app(data_handler=data_handler)
    # Run in single threaded mode to avoid data races.
    app.run(host=host, port=port, debug=debug, threaded=False)


@click.command(name="list")
@click.argument("project-path", type=click.Path(exists=True), callback=path_callback)
@click.pass_context
def list_calculated_tables(ctx: click.Context, project_path: Path) -> None:
    """List the calculated tables in the project and whether they are being overridden."""
    project = safe_get_project_from_context(ctx, project_path, read_only=True)
    scenarios = project.list_scenario_names()
    table_overrides = project.get_table_overrides()
    tables: list[str] = sorted(
        [x for x in project.list_calculated_tables() if not x.endswith("_override")]
    )

    print("Calculated tables for all scenarios:")
    for table in tables:
        print(f"  {table}")

    print("\nOverride tables by scenario:")
    for scenario in scenarios:
        print(f"  Scenario: {scenario}")
        if scenario in table_overrides:
            for override in table_overrides[scenario]:
                print(f"    {override}_override")
        else:
            print("    None")
        print()


_add_from_calculated_table_epilog = """
Examples:\n
$ stride calculated-tables override my_project \\ \n
    --scenario=custom_load_shapes \\ \n
    --table-name=energy_projection_res_load_shapes \\ \n
    --filename=custom_load_shapes.csv \n
"""


@click.command(name="override", epilog=_add_from_calculated_table_epilog)
@click.argument("project-path", type=click.Path(exists=True), callback=path_callback)
@click.option(
    "-f",
    "--filename",
    type=click.Path(exists=True),
    required=True,
    help="Filename of the new table",
    callback=path_callback,
)
@click.option("-s", "--scenario", type=str, required=True, help="Scenario name")
@click.option("-t", "--table-name", type=str, required=True, help="calculated table name")
@click.pass_context
def override_calculated_table(
    ctx: click.Context, project_path: Path, filename: Path, scenario: str, table_name: str
) -> None:
    """Override a scenario's calculated table."""
    res = handle_stride_exception(
        ctx, _override_calculated_table, project_path, filename, scenario, table_name
    )
    if res[1] != 0:
        ctx.exit(res[1])


def _override_calculated_table(
    project_path: Path, filename: Path, scenario: str, table_name: str
) -> None:
    project = Project.load(project_path)
    table = CalculatedTableOverride(
        scenario=scenario, table_name=table_name, filename=str(filename)
    )
    project.override_calculated_tables([table])


_export_calculated_table_epilog = """
Examples:\n
$ stride calculated-tables export my_project \\ \n
    --scenario=baseline \\ \n
    --table-name=energy_intensity_res_hdi_population_load_shapes \\ \n
    --filename=custom_load_shapes.csv \n
"""


@click.command(name="export", epilog=_export_calculated_table_epilog)
@click.argument("project-path", type=click.Path(exists=True), callback=path_callback)
@click.option(
    "-f",
    "--filename",
    help="Filename to create. Defaults to a CSV in the current directory. Supports CSV and "
    "Parquet, inferred from the file extension.",
    callback=path_callback,
)
@click.option(
    "--overwrite",
    default=False,
    show_default=True,
    is_flag=True,
    help="Overwrite the output directory if it exists.",
)
@click.option("-s", "--scenario", type=str, required=True, help="Scenario name")
@click.option("-t", "--table-name", type=str, required=True, help="calculated table name")
@click.pass_context
def export_calculated_table(
    ctx: click.Context,
    project_path: Path,
    filename: Path | None,
    overwrite: bool,
    scenario: str,
    table_name: str,
) -> None:
    """Export the specified calculated table to filename. Supports CSV and Parquet, inferred
    from the filename's suffix.
    """
    filename_ = Path(f"{table_name}.csv") if filename is None else filename
    res = handle_stride_exception(
        ctx,
        _export_calculated_table,
        project_path,
        scenario,
        table_name,
        filename_,
        overwrite,
    )
    if res[1] != 0:
        ctx.exit(res[1])


def _export_calculated_table(
    project_path: Path, scenario: str, table_name: str, filename: Path, overwrite: bool
) -> None:
    project = Project.load(project_path, read_only=True)
    project.export_calculated_table(scenario, table_name, filename, overwrite=overwrite)


_remove_calculated_table_epilog = """
Examples:\n
$ stride calculated-tables remove-override my_project \\ \n
    --scenario=baseline \\ \n
    --table-name=energy_intensity_res_hdi_population_load_shapes_override \\ \n
"""


@click.command(name="remove-override", epilog=_remove_calculated_table_epilog)
@click.argument("project-path", type=click.Path(exists=True), callback=path_callback)
@click.option("-s", "--scenario", type=str, required=True, help="Scenario name")
@click.option(
    "-t", "--table-name", type=str, required=True, help="Overridden calculated table name"
)
@click.pass_context
def remove_calculated_table_override(
    ctx: click.Context,
    project_path: Path,
    scenario: str,
    table_name: str,
) -> None:
    """Remove the overridden calculated table."""
    res = handle_stride_exception(
        ctx,
        _remove_calculated_table_override,
        project_path,
        scenario,
        table_name,
    )
    if res[1] != 0:
        ctx.exit(res[1])


def _remove_calculated_table_override(project_path: Path, scenario: str, table_name: str) -> None:
    project = Project.load(project_path)
    project.remove_calculated_table_overrides(
        [
            CalculatedTableOverride(
                scenario=scenario,
                table_name=table_name,
            )
        ]
    )


def handle_stride_exception(
    ctx: click.Context, func: Callable[..., Any], *args: Any, **kwargs: Any
) -> Any:
    """Handle any stride exceptions as specified by the CLI parameters."""
    res = None
    try:
        res = func(*args, **kwargs)
        return res, 0
    except (ChronifyExceptionBase, DSGBaseException):
        exc_type, exc_value, exc_tb = sys.exc_info()
        filename = exc_tb.tb_frame.f_code.co_filename  # type: ignore
        line = exc_tb.tb_lineno  # type: ignore
        msg = f'{func.__name__} failed: exception={exc_type.__name__} message="{exc_value}" {filename=} {line=}'  # type: ignore
        logger.error(msg)
        if ctx.find_root().params["reraise_exceptions"]:
            raise
        return res, 1


def safe_get_project_from_context(
    ctx: click.Context, project_path: Path, read_only: bool = False
) -> Project:
    res = handle_stride_exception(ctx, Project.load, project_path, read_only=read_only)
    if res[1] != 0:
        ctx.exit(res[1])
    project = res[0]
    assert isinstance(project, Project)
    return project


cli.add_command(projects)
cli.add_command(datasets)
cli.add_command(scenarios)
cli.add_command(calculated_tables)
cli.add_command(view)
projects.add_command(create_project)
datasets.add_command(list_datasets)
datasets.add_command(show_dataset)
scenarios.add_command(list_scenarios)
calculated_tables.add_command(list_calculated_tables)
calculated_tables.add_command(override_calculated_table)
calculated_tables.add_command(export_calculated_table)
calculated_tables.add_command(remove_calculated_table_override)
