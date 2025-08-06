from dash import Dash, html, dcc, Input, Output, State, callback
import dash_bootstrap_components as dbc
from pathlib import Path
from typing import TYPE_CHECKING

from stride.ui.layouts import create_home_tab, register_callbacks as register_home_callbacks
from stride.ui.scenario_layout import create_scenario_layout, register_scenario_callbacks
from stride.ui.color_manager import get_color_manager
from stride.ui.plotting import StridePlots
from stride.api import APIClient, Sectors, literal_to_list

if TYPE_CHECKING:
    import duckdb
    from stride.models import ProjectConfig

assets_path = Path(__file__).parent.absolute() / "assets"
app = Dash("STRIDE", title="Stride", external_stylesheets=[dbc.themes.BOOTSTRAP], assets_folder=str(assets_path), suppress_callback_exceptions=True)


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

    scenarios = data_handler.scenarios
    years = data_handler.years
    sectors = data_handler.end_uses

    # create the home view layout based on the data handler.
    # TODO, pass the entire data handler object into each "create" function.
    home_layout = create_home_tab(scenarios, literal_to_list(Sectors), years, color_manager)
    scenario_layout = create_scenario_layout(years, data_handler, color_manager)

    app.layout = html.Div([
        html.H1("STRIDE", style={"padding": "20px"}, className="stride-title"),
        dcc.Store(id="home-state-store", data={}),
        dcc.Store(id="scenario-state-store", data={}),

        html.Div([
            dbc.RadioItems(
                id="view-selector",
                className="btn-group",
                inputClassName="btn-check",
                labelClassName="btn btn-outline-primary",
                labelCheckedClassName="active",
                options=[
                    {"label": "Home", "value": "compare"},
                    *[{'label': s, 'value': s} for s in scenarios]
                ],
                value="compare",
            )
        ], className="nav-tabs"),

        html.Div([
            html.Div(id="home-view", hidden=False, children=[
                home_layout
            ]),
            html.Div(id="scenario-view", hidden=True, children=[
                scenario_layout
            ])
        ]),
    ])

    @callback(
        Output("home-view", "hidden"),
        Output("scenario-view", "hidden"),
        Input("view-selector", "value")
    )
    def toggle_views(selected_view):
        if selected_view == "compare":
            return False, True  # Show home, hide scenario
        else:
            return True, False  # Hide home, show scenario

    register_home_callbacks(data_handler, plotter, scenarios, literal_to_list(Sectors), years, color_manager)

    register_scenario_callbacks(scenarios, years, data_handler, plotter)

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
