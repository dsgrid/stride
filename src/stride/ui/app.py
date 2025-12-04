from pathlib import Path

import dash_bootstrap_components as dbc
from dash import Dash, Input, Output, callback, dcc, html

from stride.api import APIClient
from stride.api.utils import Sectors, literal_to_list
from stride.ui.color_manager import get_color_manager
from stride.ui.home import create_home_layout, register_home_callbacks
from stride.ui.plotting import StridePlots
from stride.ui.scenario import create_scenario_layout, register_scenario_callbacks

assets_path = Path(__file__).parent.absolute() / "assets"
app = Dash(
    "STRIDE",
    title="Stride",
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    assets_folder=str(assets_path),
    suppress_callback_exceptions=True,
)


def create_app(data_handler: APIClient) -> Dash:
    """
    Create the Dash application.

    Parameters
    ----------
    data_handler : APIClient
        API client with access to the project and database

    Returns
    -------
    Dash
        Configured Dash application
    """
    # Get the project's color palette
    project_palette = data_handler.project.palette

    # Initialize color manager with the project's palette
    color_manager = get_color_manager(palette=project_palette)
    color_manager.initialize_colors(
        scenarios=data_handler.scenarios,
        sectors=literal_to_list(Sectors),
        end_uses=[],  # Add end uses here if available
    )

    plotter = StridePlots(color_manager)

    scenarios = data_handler.scenarios
    years = data_handler.years

    # create the home view layout based on the data handler.
    home_layout = create_home_layout(scenarios, years, color_manager)
    scenario_layout = create_scenario_layout(years, color_manager)

    app.layout = html.Div(
        [
            html.H1("STRIDE", style={"padding": "20px"}, className="stride-title"),
            dcc.Store(id="home-state-store", data={}),
            dcc.Store(id="scenario-state-store", data={}),
            html.Div(
                [
                    dbc.RadioItems(
                        id="view-selector",
                        className="btn-group",
                        inputClassName="btn-check",
                        labelClassName="btn btn-outline-primary",
                        labelCheckedClassName="active",
                        options=[
                            {"label": "Home", "value": "compare"},
                            *[{"label": s, "value": s} for s in scenarios],
                        ],
                        value="compare",
                    )
                ],
                className="nav-tabs",
            ),
            html.Div(
                [
                    html.Div(id="home-view", hidden=False, children=[home_layout]),
                    html.Div(id="scenario-view", hidden=True, children=[scenario_layout]),
                ]
            ),
        ]
    )

    @callback(
        Output("home-view", "hidden"),
        Output("scenario-view", "hidden"),
        Input("view-selector", "value"),
    )
    def _toggle_views(selected_view: str) -> tuple[bool, bool]:
        if selected_view == "compare":
            return False, True  # Show home, hide scenario
        else:
            return True, False  # Hide home, show scenario

    register_home_callbacks(
        data_handler, plotter, scenarios, literal_to_list(Sectors), years, color_manager
    )

    register_scenario_callbacks(scenarios, years, data_handler, plotter)

    # Add a callback to save palette when app shuts down
    import atexit

    def save_palette() -> None:
        """Save the color palette back to the project on shutdown."""
        data_handler.project.save_palette()

    atexit.register(save_palette)

    return app
