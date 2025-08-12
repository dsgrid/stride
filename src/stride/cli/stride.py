import sys
from pathlib import Path
from typing import Any, Callable

import rich_click as click
from chronify.exceptions import ChronifyExceptionBase
from chronify.loggers import setup_logging
from dsgrid.exceptions import DSGBaseException
from dsgrid.cli.common import path_callback
from loguru import logger
from rich.console import Console
from rich.table import Table

from stride import Project


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
    project = safe_get_project_from_context(ctx, project_path)
    project.show_dataset(dataset_id, scenario=scenario, limit=limit)


@click.group()
def scenarios() -> None:
    """Scenario commands"""


@click.command(name="list")
@click.argument("project-path", type=click.Path(exists=True), callback=path_callback)
@click.pass_context
def list_scenarios(ctx: click.Context, project_path: Path) -> None:
    """List the scenarios stored in the project."""
    project = safe_get_project_from_context(ctx, project_path)
    scenarios = project.list_scenario_names()
    print(f"Scenarios in project with project_id={project.config.project_id}:")
    for scenario in scenarios:
        print(f"  {scenario}")


@click.group()
def calculated_tables() -> None:
    """Calculated table commands"""


@click.command(name="list")
@click.argument("project-path", type=click.Path(exists=True), callback=path_callback)
@click.option(
    "-s",
    "--scenario",
    type=str,
    help="List tables for only this scenario. Defaults to all scenarios.",
)
@click.pass_context
def list_calculated_tables(ctx: click.Context, project_path: Path, scenario: str | None) -> None:
    """List the calculated tables in the project and whether they are being overridden."""
    project = safe_get_project_from_context(ctx, project_path)
    scenarios = project.list_scenario_names() if scenario is None else [scenario]
    table_overrides = project.get_table_overrides()
    table_override_map: dict[tuple[str, str], bool] = {}
    tables: list[str] = sorted(project.list_calculated_tables())

    console_table = Table(show_header=True, title="Calculated tables, with overrides by scenario")
    console_table.add_column("table")
    for scenario in scenarios:
        console_table.add_column(scenario)
        overrides = set(table_overrides.get(scenario, []))
        for table in tables:
            table_override_map[(scenario, table)] = table in overrides

    for table in tables:
        row = [str(table_override_map[(x, table)]).lower() for x in scenarios]
        console_table.add_row(table, *row)

    console = Console()
    print()
    console.print(console_table)


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
    project.override_calculated_table(scenario, table_name, filename)


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
    project = Project.load(project_path)
    project.export_calculated_table(scenario, table_name, filename, overwrite=overwrite)


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


def safe_get_project_from_context(ctx: click.Context, project_path: Path) -> Project:
    res = handle_stride_exception(ctx, Project.load, project_path)
    if res[1] != 0:
        ctx.exit(res[1])
    project = res[0]
    assert isinstance(project, Project)
    return project


cli.add_command(projects)
cli.add_command(datasets)
cli.add_command(scenarios)
cli.add_command(calculated_tables)
projects.add_command(create_project)
datasets.add_command(list_datasets)
datasets.add_command(show_dataset)
scenarios.add_command(list_scenarios)
calculated_tables.add_command(list_calculated_tables)
calculated_tables.add_command(override_calculated_table)
calculated_tables.add_command(export_calculated_table)
