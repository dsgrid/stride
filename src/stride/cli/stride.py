import sys
from pathlib import Path
from typing import Any, Callable

import rich_click as click
from chronify.exceptions import ChronifyExceptionBase
from chronify.loggers import setup_logging
from dsgrid.exceptions import DSGBaseException
from dsgrid.cli.common import path_callback
from loguru import logger

from stride import Project, Scenario


@click.group("stride")
@click.option(
    "-c",
    "--console-level",
    default="INFO",
    show_default=True,
    help="Console log level",
)
@click.option(
    "-f",
    "--file-level",
    default="INFO",
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
$ stride create-project my_project.json5\n
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
    names = [x for x in Scenario.model_fields if x != "name"]
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
def show_dataset(project_path: Path, scenario: str, dataset_id: str, limit: int) -> None:
    """List the datasets stored in the project."""
    project = Project.load(project_path)
    project.show_dataset(dataset_id, scenario=scenario, limit=limit)


@click.group()
def scenarios() -> None:
    """Scenario commands"""


@click.command(name="list")
@click.argument("project-path", type=click.Path(exists=True), callback=path_callback)
@click.pass_context
def list_scenarios(ctx: click.Context, project_path: Path) -> None:
    """List the scenarios stored in the project."""
    res = handle_stride_exception(ctx, Project.load, project_path)
    if res[1] != 0:
        ctx.exit(res[1])
    else:
        project = res[0]
        scenarios = project.list_scenarios()
        print(" ".join(scenarios))


def handle_stride_exception(
    ctx: click.Context, func: Callable[..., Any], *args: Any, **kwargs: Any
) -> Any:
    """Handle any sparkctl exceptions as specified by the CLI parameters."""
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


cli.add_command(projects)
cli.add_command(datasets)
cli.add_command(scenarios)
projects.add_command(create_project)
datasets.add_command(list_datasets)
datasets.add_command(show_dataset)
scenarios.add_command(list_scenarios)
