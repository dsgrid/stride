from dash import Dash, html
import dash_bootstrap_components as dbc
from pathlib import Path
from typing import TYPE_CHECKING

from stride.ui.layouts import create_layout
from stride.ui.color_manager import get_color_manager
from stride.ui.plotting import StridePlots
from stride.api import APIClient, Sectors, literal_to_list

if TYPE_CHECKING:
    import duckdb
    from stride.models import ProjectConfig

assets_path = Path(__file__).parent.absolute() / "assets"
app = Dash("STRIDE", external_stylesheets=[dbc.themes.BOOTSTRAP], assets_folder=str(assets_path), suppress_callback_exceptions=True)


def create_app(project_config: 'ProjectConfig | None' = None, db_connection: 'duckdb.DuckDBPyConnection | None' = None):
    """
    Create the Dash application.

    Parameters
    ----------
    project_config : ProjectConfig, optional
        Project configuration object. If provided along with db_connection,
        will be used to initialize the APIClient.
    db_connection : duckdb.DuckDBPyConnection, optional
        Database connection object. If provided along with project_config,
        will be used to initialize the APIClient.

    Returns
    -------
    Dash
        Configured Dash application
    """
    # Initialize APIClient based on available parameters
    if project_config is not None and db_connection is not None:
        data_handler = APIClient(path_or_conn=db_connection, project_config=project_config)
    else:
        # Fallback to hardcoded path for development
        data_handler = APIClient("/home/mwebb-wsl/code/stride/stride.duckdb")

    # Initialize color manager with all entities
    color_manager = get_color_manager()
    color_manager.initialize_colors(
        scenarios=data_handler.scenarios,
        sectors=literal_to_list(Sectors),
        end_uses=[]  # Add end uses here if available
    )

    plotter = StridePlots(color_manager)

    app.layout = create_layout(data_handler, plotter, color_manager)

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
