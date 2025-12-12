from pathlib import Path
from typing import Any

import dash_bootstrap_components as dbc
from dash import Dash, Input, Output, State, callback, dcc, html
from dash.exceptions import PreventUpdate
from loguru import logger

from stride.api import APIClient
from stride.api.utils import Sectors, literal_to_list
from stride.ui.color_manager import ColorManager, get_color_manager
from stride.ui.home import create_home_layout, register_home_callbacks
from stride.ui.palette import ColorPalette
from stride.ui.plotting import StridePlots
from stride.ui.project_manager import add_recent_project, discover_projects, load_project_by_path
from stride.ui.scenario import create_scenario_layout, register_scenario_callbacks
from stride.ui.settings import create_settings_layout, register_settings_callbacks
from stride.ui.tui import list_user_palettes

assets_path = Path(__file__).parent.absolute() / "assets"
app = Dash(
    "STRIDE",
    title="Stride",
    external_stylesheets=[
        dbc.themes.BOOTSTRAP,
        "https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.0/font/bootstrap-icons.css",
    ],
    assets_folder=str(assets_path),
    suppress_callback_exceptions=True,
)


# Global state for loaded projects
_loaded_projects = {}  # project_path -> (data_handler, color_manager, plotter)
_current_project_path = None


def create_app(  # noqa: C901
    data_handler: APIClient,
    user_palette: ColorPalette | None = None,
    available_projects: list[dict[str, str]] | None = None,
) -> Dash:
    """
    Create the Dash application.

    Parameters
    ----------
    data_handler : APIClient
        API client with access to the project and database
    user_palette : ColorPalette | None, optional
        User palette to override the project palette. If None, uses the project palette.
    available_projects : list[dict[str, str]] | None, optional
        List of available projects for the project switcher dropdown

    Returns
    -------
    Dash
        Configured Dash application
    """
    global _loaded_projects, _current_project_path

    # Store initial project
    current_project_path = str(data_handler.project.path)
    _current_project_path = current_project_path

    # Determine palette type
    if user_palette is not None:
        palette = user_palette
        current_palette_type = "user"
        # Try to find the palette name from user palettes
        try:
            user_palette_list = list_user_palettes()
            current_palette_name = user_palette_list[0].stem if user_palette_list else None
        except Exception:
            current_palette_name = None
    else:
        palette = data_handler.project.palette
        current_palette_type = "project"
        current_palette_name = None

    # Initialize color manager with the selected palette
    color_manager = get_color_manager(palette=palette)
    color_manager.initialize_colors(
        scenarios=data_handler.scenarios,
        sectors=literal_to_list(Sectors),
        end_uses=[],  # Add end uses here if available
    )

    plotter = StridePlots(color_manager, template="plotly_dark")

    # Store in global cache
    _loaded_projects[current_project_path] = (data_handler, color_manager, plotter)

    scenarios = data_handler.scenarios
    years = data_handler.years

    # Discover available projects if not provided
    if available_projects is None:
        try:
            available_projects = discover_projects()
        except Exception as e:
            logger.warning(f"Could not discover projects: {e}")
            available_projects = []

    # Add current project to recent projects
    try:
        add_recent_project(
            data_handler.project.path,
            data_handler.project.config.project_id,
        )
    except Exception as e:
        logger.warning(f"Could not add to recent projects: {e}")

    # Create the home view layout
    home_layout = create_home_layout(scenarios, years, color_manager)
    scenario_layout = create_scenario_layout(years, color_manager)

    # Create settings layout
    try:
        user_palettes_paths = list_user_palettes()
        # Extract just the palette names (without .json extension)
        user_palettes = [p.stem for p in user_palettes_paths]
    except Exception as e:
        logger.warning(f"Could not list user palettes: {e}")
        user_palettes = []

    project_palette_name = data_handler.project.config.project_id
    settings_layout = create_settings_layout(
        project_palette_name=project_palette_name,
        user_palettes=user_palettes,
        current_palette_type=current_palette_type,
        current_palette_name=current_palette_name,
        color_manager=color_manager,
    )

    # Create project options for dropdown
    project_options = [
        {"label": p["display_name"], "value": p["path"]} for p in available_projects
    ]

    # Create sidebar
    sidebar = html.Div(
        [
            html.Div(
                [
                    html.H4("Navigation", className="text-white mb-4"),
                    html.Hr(className="bg-white"),
                    # Projects section
                    html.Div(
                        [
                            html.H6("Projects", className="text-white-50 mb-2"),
                            dcc.Dropdown(
                                id="sidebar-project-selector",
                                options=project_options,  # type: ignore[arg-type]
                                value=current_project_path,
                                clearable=False,
                                className="mb-3",
                            ),
                        ]
                    ),
                    html.Hr(className="bg-white"),
                    # Settings link
                    html.Div(
                        [
                            dbc.Button(
                                [html.I(className="bi bi-gear me-2"), "Settings"],
                                id="sidebar-settings-btn",
                                color="light",
                                outline=True,
                                className="w-100",
                            ),
                        ]
                    ),
                ],
                className="p-3",
            ),
        ],
        id="sidebar",
        className="sidebar-nav dark-theme",
        style={
            "position": "fixed",
            "top": 0,
            "left": 0,
            "bottom": 0,
            "width": "250px",
            "zIndex": 1000,
            "transform": "translateX(-250px)",
            "transition": "transform 0.3s ease-in-out",
            "overflowY": "auto",
        },
    )

    # Main content wrapper
    app.layout = html.Div(
        [
            # Stores for state management
            dcc.Store(id="home-state-store", data={}),
            dcc.Store(id="scenario-state-store", data={}),
            dcc.Store(
                id="settings-palette-applied",
                data={"type": current_palette_type, "name": current_palette_name},
            ),
            dcc.Store(id="current-project-path", data=current_project_path),
            dcc.Store(id="sidebar-open", data=False),
            dcc.Store(id="chart-refresh-trigger", data=0),
            dcc.Store(id="theme-store", data="dark"),
            # Dynamic scenario CSS that updates with palette changes
            html.Div(
                id="scenario-css-container",
                children=[
                    html.Script(
                        f"""
                        (function() {{
                            var existingStyle = document.getElementById('scenario-dynamic-css');
                            if (existingStyle) {{
                                existingStyle.remove();
                            }}
                            var style = document.createElement('style');
                            style.id = 'scenario-dynamic-css';
                            style.textContent = `{color_manager.generate_scenario_css()}`;
                            document.head.appendChild(style);
                        }})();
                        """
                    )
                ],
                style={"display": "none"},
            ),
            # Sidebar
            sidebar,
            # Main content
            html.Div(
                [
                    # Header
                    html.Div(
                        [
                            dbc.Row(
                                [
                                    dbc.Col(
                                        [
                                            html.Div(
                                                [
                                                    html.Div(
                                                        dbc.Button(
                                                            html.Span(
                                                                "›",
                                                                style={
                                                                    "fontSize": "1.5rem",
                                                                    "fontWeight": "bold",
                                                                },
                                                            ),
                                                            id="sidebar-toggle",
                                                            className="me-3 sidebar-toggle-btn",
                                                        ),
                                                        className="sidebar-toggle-wrapper",
                                                    ),
                                                    html.Div(
                                                        [
                                                            html.H1(
                                                                "STRIDE",
                                                                id="home-link",
                                                                className="stride-title",
                                                                style={
                                                                    "display": "inline-block",
                                                                    "margin": 0,
                                                                    "cursor": "pointer",
                                                                },
                                                            ),
                                                        ],
                                                        style={"display": "inline-block"},
                                                    ),
                                                ],
                                                style={
                                                    "display": "flex",
                                                    "alignItems": "center",
                                                    "padding": "20px",
                                                },
                                            ),
                                        ],
                                        width=6,
                                    ),
                                    dbc.Col(
                                        [
                                            html.Div(
                                                [
                                                    html.Span(
                                                        "☀",
                                                        className="theme-icon sun-icon",
                                                        style={
                                                            "fontSize": "1.4rem",
                                                            "marginRight": "15px",
                                                        },
                                                    ),
                                                    dbc.Switch(
                                                        id="theme-toggle",
                                                        value=True,
                                                        style={
                                                            "transform": "scale(1.2)",
                                                        },
                                                    ),
                                                    html.Span(
                                                        "☾",
                                                        className="theme-icon moon-icon",
                                                        style={
                                                            "fontSize": "1.4rem",
                                                            "marginLeft": "0px",
                                                        },
                                                    ),
                                                ],
                                                style={
                                                    "display": "flex",
                                                    "alignItems": "center",
                                                    "justifyContent": "flex-end",
                                                    "padding": "20px",
                                                },
                                            ),
                                        ],
                                        width=6,
                                    ),
                                ],
                            ),
                        ],
                        id="header-container",
                    ),
                    # Navigation tabs
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
                        id="nav-tabs-container",
                    ),
                    # Main content area
                    html.Div(
                        [
                            html.Div(id="home-view", hidden=False, children=[home_layout]),
                            html.Div(id="scenario-view", hidden=True, children=[scenario_layout]),
                            html.Div(id="settings-view", hidden=True, children=[settings_layout]),
                        ],
                        id="main-content-container",
                    ),
                ],
                id="page-content",
                className="page-content dark-theme",
                style={"marginLeft": "0px", "transition": "margin-left 0.3s"},
            ),
        ],
        className="dark-theme",
        style={"minHeight": "100vh"},
    )

    # Sidebar toggle callback
    @callback(
        Output("sidebar", "style"),
        Output("page-content", "style"),
        Output("sidebar-open", "data"),
        Output("sidebar-toggle", "children"),
        Input("sidebar-toggle", "n_clicks"),
        State("sidebar-open", "data"),
        prevent_initial_call=True,
    )
    def toggle_sidebar(n_clicks, is_open):  # type: ignore[no-untyped-def]
        """Toggle sidebar visibility."""
        if n_clicks is None:
            return (
                {},
                {},
                is_open,
                html.Span("›", style={"fontSize": "1.5rem", "fontWeight": "bold"}),
            )

        new_state = not is_open

        # Update button icon based on state
        button_icon = (
            html.Span("‹", style={"fontSize": "1.5rem", "fontWeight": "bold"})
            if new_state
            else html.Span("›", style={"fontSize": "1.5rem", "fontWeight": "bold"})
        )

        if new_state:
            # Open sidebar
            sidebar_style = {
                "position": "fixed",
                "top": 0,
                "left": 0,
                "bottom": 0,
                "width": "250px",
                "zIndex": 1000,
                "transform": "translateX(0px)",
                "transition": "transform 0.3s ease-in-out",
                "overflowY": "auto",
            }
            content_style = {"marginLeft": "250px", "transition": "margin-left 0.3s"}
        else:
            # Close sidebar
            sidebar_style = {
                "position": "fixed",
                "top": 0,
                "left": 0,
                "bottom": 0,
                "width": "250px",
                "zIndex": 1000,
                "transform": "translateX(-250px)",
                "transition": "transform 0.3s ease-in-out",
                "overflowY": "auto",
            }
            content_style = {"marginLeft": "0px", "transition": "margin-left 0.3s"}

        return sidebar_style, content_style, new_state, button_icon

    # Project switching callback
    @callback(
        Output("current-project-path", "data"),
        Output("nav-tabs-container", "children"),
        Output("home-view", "children"),
        Output("scenario-view", "children"),
        Input("sidebar-project-selector", "value"),
        State("current-project-path", "data"),
        prevent_initial_call=True,
    )
    def switch_project(new_project_path, current_path):  # type: ignore[no-untyped-def]
        """Switch to a different project by loading it dynamically."""
        global _loaded_projects

        if new_project_path == current_path or new_project_path is None:
            from dash.exceptions import PreventUpdate

            raise PreventUpdate

        logger.info(f"Switching from {current_path} to {new_project_path}")

        try:
            # Check if project is already loaded
            if new_project_path in _loaded_projects:
                logger.info(f"Using cached project: {new_project_path}")
                data_handler, color_manager, plotter = _loaded_projects[new_project_path]
            else:
                logger.info(f"Loading new project: {new_project_path}")
                # Load the new project
                project = load_project_by_path(new_project_path, read_only=True)
                data_handler = APIClient(project=project)

                # Initialize color manager
                palette = data_handler.project.palette
                color_manager = get_color_manager(palette=palette)
                color_manager.initialize_colors(
                    scenarios=data_handler.scenarios,
                    sectors=literal_to_list(Sectors),
                    end_uses=[],
                )

                plotter = StridePlots(color_manager, template="plotly_dark")

                # Cache it
                _loaded_projects[new_project_path] = (data_handler, color_manager, plotter)

            # Add to recent projects
            try:
                add_recent_project(
                    data_handler.project.path,
                    data_handler.project.config.project_id,
                )
            except Exception as e:
                logger.warning(f"Could not add to recent projects: {e}")

            # Get new project data
            scenarios = data_handler.scenarios
            years = data_handler.years

            # Create new layouts
            home_layout = create_home_layout(scenarios, years, color_manager)
            scenario_layout = create_scenario_layout(years, color_manager)

            # Create new nav tabs
            nav_tabs = dbc.RadioItems(
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

            # Re-register callbacks for new data
            register_home_callbacks(
                data_handler, plotter, scenarios, literal_to_list(Sectors), years, color_manager
            )
            register_scenario_callbacks(scenarios, years, data_handler, plotter)

            logger.info(f"Successfully switched to project: {new_project_path}")

            return new_project_path, nav_tabs, home_layout, scenario_layout

        except Exception as e:
            logger.error(f"Error switching project: {e}")
            from dash.exceptions import PreventUpdate

            raise PreventUpdate

    # View toggle callback
    @callback(
        Output("home-view", "hidden"),
        Output("scenario-view", "hidden"),
        Output("settings-view", "hidden"),
        Output("nav-tabs-container", "style"),
        Output("view-selector", "value"),
        Output("chart-refresh-trigger", "data"),
        Input("view-selector", "value"),
        Input("sidebar-settings-btn", "n_clicks"),
        Input("back-to-dashboard-btn", "n_clicks"),
        Input("home-link", "n_clicks"),
        State("settings-view", "hidden"),
        State("chart-refresh-trigger", "data"),
        prevent_initial_call="initial_duplicate",
    )
    def toggle_views(
        selected_view: str,
        settings_clicks: int | None,
        back_clicks: int | None,
        home_clicks: int | None,
        settings_hidden: bool,
        current_refresh_count: int,
    ) -> tuple[bool, bool, bool, dict[str, str], str, int]:
        """Toggle between home, scenario, and settings views."""
        from dash import ctx

        # Check which input triggered the callback
        trigger_id = ctx.triggered_id if ctx.triggered_id else None

        if trigger_id == "sidebar-settings-btn":
            # Show settings, hide everything else
            return (
                True,
                True,
                False,
                {"display": "none"},
                selected_view,
                current_refresh_count,
            )
        elif trigger_id == "back-to-dashboard-btn" or trigger_id == "home-link":
            # Return to home view - apply any temporary color edits and refresh charts
            from stride.ui.settings.layout import get_temp_color_edits

            # Apply temporary color edits to the ColorManager
            temp_edits = get_temp_color_edits()
            if temp_edits:
                color_manager = get_current_color_manager()
                if color_manager:
                    palette = color_manager.get_palette()
                    for label, color in temp_edits.items():
                        palette.update(label, color)
                    logger.info(
                        f"Applied {len(temp_edits)} temporary color edits when returning to home"
                    )

            return (
                False,
                True,
                True,
                {"display": "block"},
                "compare",
                current_refresh_count + 1,
            )
        else:
            # Normal view selection
            if selected_view == "compare":
                return (
                    False,
                    True,
                    True,
                    {"display": "block"},
                    selected_view,
                    current_refresh_count,
                )
            else:
                return (
                    True,
                    False,
                    True,
                    {"display": "block"},
                    selected_view,
                    current_refresh_count,
                )

    # Theme toggle callback
    @callback(
        Output("page-content", "className"),
        Output("sidebar", "className"),
        Output("theme-store", "data"),
        Output("chart-refresh-trigger", "data", allow_duplicate=True),
        Input("theme-toggle", "value"),
        State("chart-refresh-trigger", "data"),
        prevent_initial_call=True,
    )
    def toggle_theme(is_dark: bool, refresh_count: int) -> tuple[str, str, str, int]:
        """Toggle between light and dark theme."""
        theme = "dark-theme" if is_dark else "light-theme"

        # Update plotter template for all charts
        if plotter:
            template = "plotly_dark" if is_dark else "plotly_white"
            plotter.set_template(template)
            logger.info(f"Switched to {theme} with plot template {template}")

        # Note: For OS theme detection, add clientside callback with:
        # window.matchMedia('(prefers-color-scheme: dark)').matches

        return theme, f"sidebar-nav {theme}", theme, refresh_count + 1

    # Helper function for palette changes  # type: ignore[arg-type]
    def on_palette_change(palette: ColorPalette, palette_type: str, palette_name: str | None):  # type: ignore[no-untyped-def]
        """Update the color manager when palette changes."""
        global _loaded_projects, _current_project_path

        if _current_project_path in _loaded_projects:
            data_handler, _, _ = _loaded_projects[_current_project_path]

            # Reinitialize color manager with new palette
            color_manager = get_color_manager(palette=palette)
            color_manager.initialize_colors(
                scenarios=data_handler.scenarios,
                sectors=literal_to_list(Sectors),
                end_uses=[],
            )

            plotter = StridePlots(color_manager, template="plotly_dark")

            # Update cache
            _loaded_projects[_current_project_path] = (data_handler, color_manager, plotter)

            logger.info(f"Palette changed to: {palette_type} / {palette_name}")

    # Helper function to get color manager
    def get_current_color_manager() -> ColorManager | None:
        """Get the current color manager instance."""
        if _current_project_path in _loaded_projects:
            _, color_manager, _ = _loaded_projects[_current_project_path]
            return color_manager
        return None

    # Helper function to get data handler
    def get_current_data_handler() -> "APIClient | None":
        """Get the current data handler instance."""
        if _current_project_path in _loaded_projects:
            data_handler, _, _ = _loaded_projects[_current_project_path]
            return data_handler
        return None

    # Register callbacks
    register_home_callbacks(
        data_handler, plotter, scenarios, literal_to_list(Sectors), years, color_manager
    )

    register_scenario_callbacks(scenarios, years, data_handler, plotter)

    register_settings_callbacks(
        get_current_data_handler,
        get_current_color_manager,
        on_palette_change,
    )

    # Callback to update scenario CSS when palette changes
    @callback(
        Output("scenario-css-container", "children"),
        Input("settings-palette-applied", "data"),
    )
    def update_scenario_css(palette_data: dict[str, Any]) -> list:
        """Update scenario CSS when palette changes."""
        color_manager = get_current_color_manager()
        if color_manager is None:
            raise PreventUpdate
        return [
            html.Script(
                f"""
                (function() {{
                    var existingStyle = document.getElementById('scenario-dynamic-css');
                    if (existingStyle) {{
                        existingStyle.remove();
                    }}
                    var style = document.createElement('style');
                    style.id = 'scenario-dynamic-css';
                    style.textContent = `{color_manager.generate_scenario_css()}`;
                    document.head.appendChild(style);
                }})();
                """
            )
        ]

    return app
