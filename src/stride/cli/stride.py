import sys
from pathlib import Path
from typing import Any, Callable

import rich_click as click
from chronify.exceptions import ChronifyExceptionBase
from chronify.loggers import setup_logging
from dsgrid.exceptions import DSGBaseException
from dsgrid.cli.common import path_callback
from loguru import logger

from stride.project import Project


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


_create_epilog = """
Examples:\n
$ stride create-project my_project.json5\n
"""


@click.command(epilog=_create_epilog)
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
def create_project(
    ctx: click.Context, config_file: Path, directory: Path, overwrite: bool
) -> None:
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
        return res[1]


_add_scenario_epilog = """
Examples:\n
$ stride add-scenario new_scenario.json5 my_project_dir\n
"""


@click.command(epilog=_add_scenario_epilog)
@click.argument("config_file", type=click.Path(exists=True), callback=path_callback)
@click.argument("project_dir", type=click.Path(exists=True), callback=path_callback)
@click.pass_context
def add_scenario(ctx: click.Context, config_file: Path, project_dir: Path) -> None:
    """Add a scenario to an existing project."""


def handle_stride_exception(ctx: click.Context, func: Callable, *args, **kwargs) -> Any:
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


cli.add_command(create_project)
cli.add_command(add_scenario)
