import sys
from pathlib import Path
from typing import Any, Callable

import rich_click as click
from chronify.exceptions import ChronifyExceptionBase
from chronify.loggers import setup_logging
from dsgrid.cli.common import path_callback
from dsgrid.exceptions import DSGBaseException
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
    default="DEBUG",
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
    setup_logging(
        filename="stride.log",
        console_level=console_level,
        file_level=file_level,
        mode="a",
    )


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
    res = handle_stride_exception(
        ctx, Project.create, config_file, base_dir=directory, overwrite=overwrite
    )
    if res[1] != 0:
        ctx.exit(res[1])


_export_ep_epilog = """
Examples:\n
$ stride projects export-energy-projection test_project\n
$ stride projects export-energy-projection test_project -f energy_projection.parquet \n
"""


@click.command(name="export-energy-projection", epilog=_export_ep_epilog)
@click.argument("project_path", type=click.Path(exists=True), callback=path_callback)
@click.option(
    "-f",
    "--filename",
    type=click.Path(),
    default="energy_projection.csv",
    show_default=True,
    help="Exported filename. Supports .csv and .parquet.",
    callback=path_callback,
)
@click.option(
    "--overwrite",
    default=False,
    show_default=True,
    is_flag=True,
    help="Overwrite the exported filename if it exists.",
)
@click.pass_context
def export_energy_projection(
    ctx: click.Context, project_path: Path, filename: Path, overwrite: bool
) -> None:
    """Export the energy projection table to a file."""
    project = safe_get_project_from_context(ctx, project_path, read_only=True)
    project.export_energy_projection(filename=filename, overwrite=overwrite)


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
    """Print a limited number of rows of the dataset to the console."""
    project = safe_get_project_from_context(ctx, project_path, read_only=True)
    project.show_dataset(scenario, dataset_id, limit=limit)


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
@click.option(
    "--user-palette",
    type=str,
    default=None,
    help="Override project palette with a user palette",
)
@click.option(
    "--no-default-palette",
    is_flag=True,
    default=False,
    help="Disable automatic loading of default user palette",
)
@click.pass_context
def view(
    ctx: click.Context,
    project_path: Path,
    host: str,
    port: int,
    debug: bool,
    user_palette: str | None,
    no_default_palette: bool,
) -> None:
    """Start the STRIDE dashboard UI for the specified project.

    By default, if a default user palette is set, it will override the project palette.
    Use --no-default-palette to disable this behavior, or --user-palette to specify
    a different user palette to use.
    """
    from stride.api import APIClient
    from stride.ui.app import create_app
    from stride.ui.project_manager import discover_projects
    from stride.ui.tui import get_default_user_palette, load_user_palette

    project = safe_get_project_from_context(ctx, project_path)

    # Determine which palette to use
    palette_override = None
    palette_name = None

    if user_palette:
        # Explicit user palette override
        palette_name = user_palette
    elif not no_default_palette:
        # Check for default user palette
        palette_name = get_default_user_palette()

    if palette_name:
        try:
            palette_override = load_user_palette(palette_name)
            logger.info(f"Using user palette: {palette_name}")
            print(f"Using user palette: {palette_name}")
        except FileNotFoundError:
            logger.error(f"User palette '{palette_name}' not found")
            ctx.exit(1)

    # Discover available projects for the project switcher
    try:
        available_projects = discover_projects()
        logger.info(f"Discovered {len(available_projects)} projects")
    except Exception as e:
        logger.warning(f"Could not discover projects: {e}")
        available_projects = []

    data_handler = APIClient(project=project)

    app = create_app(
        data_handler=data_handler,
        user_palette=palette_override,
        available_projects=available_projects,
    )
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


@click.command(name="show")
@click.argument("project-path", type=click.Path(exists=True), callback=path_callback)
@click.argument("table", type=str)
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
def show_calculated_table(
    ctx: click.Context, project_path: Path, scenario: str, table: str, limit: int
) -> None:
    """Print a limited number of rows of the table to the console."""
    project = safe_get_project_from_context(ctx, project_path, read_only=True)
    project.show_calculated_table(scenario, table, limit=limit)


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
    table = CalculatedTableOverride(scenario=scenario, table_name=table_name, filename=filename)
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


@click.group()
def palette() -> None:
    """Palette commands"""


_palette_view_epilog = """
Examples:\n
$ stride palette view test_project --project\n
$ stride palette view my_palette --user\n
"""


@click.command(name="view", epilog=_palette_view_epilog)
@click.argument("name", type=str)
@click.option(
    "--project",
    "palette_type",
    flag_value="project",
    default=True,
    help="View a project palette (default)",
)
@click.option(
    "--user",
    "palette_type",
    flag_value="user",
    help="View a user palette",
)
@click.pass_context
def view_palette(ctx: click.Context, name: str, palette_type: str) -> None:
    """View a color palette in an interactive TUI.

    For project palettes, NAME should be the path to the project directory.
    For user palettes, NAME should be the palette name.
    """
    from stride.ui.tui import launch_palette_viewer

    if palette_type == "project":
        project_path = Path(name)
        if not project_path.exists():
            logger.error(f"Project path does not exist: {project_path}")
            ctx.exit(1)

        palette_file = project_path / "project.json5"
        if not palette_file.exists():
            logger.error(f"Project config not found: {palette_file}")
            ctx.exit(1)

        # Load project config to get better grouping info
        from stride.models import ProjectConfig

        config = ProjectConfig.from_file(palette_file)

        launch_palette_viewer(palette_file, palette_type="project", project_config=config)
    else:
        from stride.ui.tui import get_user_palette_dir

        palette_dir = get_user_palette_dir()
        palette_file = palette_dir / f"{name}.json"

        if not palette_file.exists():
            logger.error(f"User palette not found: {palette_file}")
            ctx.exit(1)

        launch_palette_viewer(palette_file, palette_type="user")


_palette_init_epilog = """
Examples:\n
# Create an empty palette (for manual population)\n
$ stride palette init --name=my_palette --user\n
\n
# Initialize from project (queries database for unique labels)\n
$ stride palette init --name=my_palette --from-project=test_project\n
\n
# Initialize from existing user palette\n
$ stride palette init --name=my_palette --from-user=base_palette\n
\n
# Save to user (default) or project location\n
$ stride palette init --name=my_palette --from-project=test_project --user\n
$ stride palette init --name=my_palette --from-project=test_project --project\n
"""


@click.command(name="init", epilog=_palette_init_epilog)
@click.option(
    "--name",
    type=str,
    required=True,
    help="Name for the new palette",
)
@click.option(
    "--from-project",
    type=click.Path(exists=True),
    callback=path_callback,
    help="Initialize from project (query database for labels or copy existing palette)",
)
@click.option(
    "--from-user",
    type=str,
    help="Copy from an existing user palette",
)
@click.option(
    "--project",
    "palette_type",
    flag_value="project",
    help="Save to project palette (requires --from-project)",
)
@click.option(
    "--user",
    "palette_type",
    flag_value="user",
    default=True,
    help="Save to user palette (default)",
)
@click.pass_context
def init_palette(
    ctx: click.Context,
    name: str,
    from_project: Path | None,
    from_user: str | None,
    palette_type: str,
) -> None:
    """Initialize a new palette with colors assigned to labels.

    Sources (optional):

    --from-project: Initialize from a project (queries database for unique labels or copies existing palette)

    --from-user: Copy from an existing user palette in ~/.stride/palettes/

    (No source): Create an empty palette for manual population via TUI

    The palette can be saved to user space (default) or embedded in a project.
    """
    from stride.api import APIClient
    from stride.ui.palette import ColorPalette
    from stride.ui.tui import load_user_palette, save_user_palette

    # Validate that at most one source is specified
    sources = [from_project, from_user]
    source_count = sum(1 for s in sources if s is not None)

    if source_count > 1:
        logger.error("You can only specify one source at a time")
        ctx.exit(1)

    # Validate palette_type requirements
    if palette_type == "project" and not from_project:
        logger.error("--project requires --from-project (need a project context)")
        ctx.exit(1)

    # Initialize palette based on source type
    palette_dict: dict[str, str] = {}
    project_path: Path | None = None

    if source_count == 0:
        # Create an empty palette
        print(f"Creating empty palette: {name}")
        print("Use 'stride palette view {name} --user' to add labels interactively")
        palette_dict = {}
    elif from_project:
        # Query the database for all unique labels
        project_path = from_project
        print(f"Querying database for unique labels in project: {project_path}")
        project = safe_get_project_from_context(ctx, project_path, read_only=True)
        api_client = APIClient(project)

        # Get all unique labels
        scenarios = api_client.scenarios
        years = [str(y) for y in api_client.years]
        sectors = api_client.get_unique_sectors()
        end_uses = api_client.get_unique_end_uses()

        print(
            f"Found {len(scenarios)} scenarios, {len(years)} years, {len(sectors)} sectors, {len(end_uses)} end uses"
        )

        # Create a new palette with all labels
        palette = ColorPalette()
        all_labels = scenarios + years + sectors + end_uses

        for label in all_labels:
            # This will automatically assign colors from the theme
            palette.get(label)

        palette_dict = palette.to_dict()

    elif from_user:
        # Load from existing user palette
        print(f"Loading user palette: {from_user}")
        try:
            source_palette = load_user_palette(from_user)
            palette_dict = source_palette.to_dict()
            print(f"Loaded {len(palette_dict)} colors from user palette '{from_user}'")
        except FileNotFoundError:
            logger.error(f"User palette not found: {from_user}")
            ctx.exit(1)

    # Save the palette to the target location
    if palette_type == "user":
        # Save to user directory
        saved_path = save_user_palette(name, palette_dict)
        logger.info(f"Created user palette '{name}' at {saved_path}")
        print(f"\nCreated user palette: {saved_path}")
        print(f"View with: stride palette view {name} --user")
    else:
        # Save to project palette
        if not project_path:
            logger.error("Project path not available for --project destination")
            ctx.exit(1)
        project = safe_get_project_from_context(ctx, project_path, read_only=False)
        project.config.color_palette = palette_dict
        project.persist()
        logger.info(f"Created project palette in {project_path / 'project.json5'}")
        print(f"\nCreated project palette in: {project_path / 'project.json5'}")
        print(f"View with: stride palette view {project_path} --project")


@click.command(name="list")
@click.option(
    "--project",
    "palette_type",
    flag_value="project",
    help="List project palettes (requires project path)",
)
@click.option(
    "--user",
    "palette_type",
    flag_value="user",
    default=True,
    help="List user palettes (default)",
)
def list_palettes(palette_type: str) -> None:
    """List available color palettes."""
    if palette_type == "user":
        from stride.ui.tui import list_user_palettes

        palettes = list_user_palettes()
        if not palettes:
            print("No user palettes found.")
            print(
                "Create one with: stride palette init <project_path> --name=<palette_name> --user"
            )
        else:
            print("User palettes:")
            for palette_path in palettes:
                print(f"  - {palette_path.stem} ({palette_path})")
    else:
        print("To view a project palette, use: stride palette view <project_path> --project")


@click.command(name="set-default")
@click.argument("palette-name", type=str, required=False)
@click.pass_context
def set_default_palette(ctx: click.Context, palette_name: str | None) -> None:
    """Set or clear the default user palette.

    The default user palette will be automatically used when starting the dashboard
    unless overridden with --user-palette option.

    Examples:

    Set a default palette:
    $ stride palette set-default my_palette

    Clear the default palette:
    $ stride palette set-default
    """
    from stride.ui.tui import set_default_user_palette

    try:
        set_default_user_palette(palette_name)
        if palette_name:
            print(f"Default user palette set to: {palette_name}")
            print("This palette will be used when starting the dashboard unless overridden.")
        else:
            print("Default user palette cleared.")
    except FileNotFoundError as e:
        logger.error(str(e))
        ctx.exit(1)


@click.command(name="get-default")
def get_default_palette() -> None:
    """Show the current default user palette.

    Examples:

    $ stride palette get-default
    """
    from stride.ui.tui import get_default_user_palette

    default = get_default_user_palette()
    if default:
        print(f"Default user palette: {default}")
    else:
        print("No default user palette set.")
        print("Set one with: stride palette set-default <palette-name>")


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
cli.add_command(palette)
cli.add_command(view)
projects.add_command(create_project)
projects.add_command(export_energy_projection)
datasets.add_command(list_datasets)
datasets.add_command(show_dataset)
scenarios.add_command(list_scenarios)
calculated_tables.add_command(list_calculated_tables)
calculated_tables.add_command(show_calculated_table)
calculated_tables.add_command(override_calculated_table)
calculated_tables.add_command(export_calculated_table)
calculated_tables.add_command(remove_calculated_table_override)
palette.add_command(view_palette)
palette.add_command(init_palette)
palette.add_command(list_palettes)
palette.add_command(set_default_palette)
palette.add_command(get_default_palette)
