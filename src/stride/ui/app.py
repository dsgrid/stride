from __future__ import annotations

from pathlib import Path
from typing import Any

import dash_bootstrap_components as dbc
from dash import Dash, Input, Output, State, callback, dcc, html
from dash.exceptions import PreventUpdate
from loguru import logger


from stride.api import APIClient
from stride.api.utils import Sectors, literal_to_list
from stride.project import Project
from stride.ui.color_manager import ColorManager
from stride.ui.home import create_home_layout, register_home_callbacks
from stride.ui.palette import ColorPalette
from stride.ui.plotting import StridePlots
from stride.ui.project_manager import add_recent_project, get_recent_projects
from stride.ui.scenario import create_scenario_layout, register_scenario_callbacks
from stride.ui.settings import create_settings_layout, register_settings_callbacks
from stride.ui.settings.layout import get_temp_color_edits
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
# project_path -> (project, color_manager, plotter, project_name)
# Note: We store Project instead of APIClient because APIClient is a singleton
_loaded_projects: dict[str, tuple[Project, ColorManager, StridePlots, str]] = {}
_current_project_path: str | None = None


def create_fresh_color_manager(palette: ColorPalette, scenarios: list[str]) -> ColorManager:
    """Create a fresh ColorManager instance, bypassing the singleton.

    Each project needs its own ColorManager to ensure consistent colors.
    """
    from itertools import cycle

    # Reset the palette's iterators to ensure consistent color assignment
    palette._scenario_iterator = cycle(palette.scenario_theme)
    palette._model_year_iterator = cycle(palette.model_year_theme)
    palette._metric_iterator = cycle(palette.metric_theme)

    # Use object.__new__ to bypass ColorManager's singleton __new__ method
    color_manager = object.__new__(ColorManager)
    color_manager._initialized = False
    color_manager._scenario_colors = {}
    ColorManager.__init__(color_manager, palette)
    color_manager.initialize_colors(
        scenarios=scenarios,
        sectors=literal_to_list(Sectors),
        end_uses=[],
    )

    return color_manager


def load_project(project_path: str) -> tuple[bool, str]:
    """
    Load a project from the given path.

    Parameters
    ----------
    project_path : str
        Path to the project directory

    Returns
    -------
    tuple[bool, str]
        (success, message) where success is True if loaded successfully
    """
    global _loaded_projects, _current_project_path

    try:
        path = Path(project_path).resolve()
        path_str = str(path)

        # Check if already loaded - just switch to it
        if path_str in _loaded_projects:
            _current_project_path = path_str
            # Update the APIClient singleton to point to this project
            cached_project, _, _, project_name = _loaded_projects[path_str]
            APIClient(cached_project)  # Updates singleton
            return True, f"Switched to cached project: {project_name}"

        # Load new project
        project = Project.load(path, read_only=True)
        data_handler = APIClient(project)  # Updates singleton

        # Create a fresh color manager for this project
        palette = project.palette.copy()
        color_manager = create_fresh_color_manager(palette, data_handler.scenarios)

        plotter = StridePlots(color_manager, template="plotly_dark")

        project_name = project.config.project_id

        # Cache Project (not APIClient) since APIClient is singleton
        _loaded_projects[path_str] = (project, color_manager, plotter, project_name)
        _current_project_path = path_str

        # Add to recent projects
        try:
            add_recent_project(path, project.config.project_id)
        except Exception as e:
            logger.warning(f"Could not add to recent projects: {e}")

        return True, f"Loaded project: {project_name}"

    except Exception as e:
        logger.error(f"Failed to load project from {project_path}: {e}")
        return False, str(e)


def get_loaded_project_options() -> list[dict[str, str]]:
    """Get dropdown options for loaded projects."""
    options = []
    for path_str, cached_tuple in _loaded_projects.items():
        # Use stored project_name (index 3) since APIClient is singleton
        project_name = cached_tuple[3] if len(cached_tuple) > 3 else "Unknown"
        options.append({"label": project_name, "value": path_str})
    return options


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

    # Store initial project - resolve to absolute path for consistency
    current_project_path = str(Path(data_handler.project.path).resolve())
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

    # Create fresh color manager for this project
    color_manager = create_fresh_color_manager(palette.copy(), data_handler.scenarios)

    plotter = StridePlots(color_manager, template="plotly_dark")

    # Store in global cache - store Project (not APIClient) since APIClient is singleton
    initial_project_name = data_handler.project.config.project_id
    initial_project = data_handler.project  # Get reference before it changes
    _loaded_projects[current_project_path] = (
        initial_project,  # Store Project, not APIClient
        color_manager,
        plotter,
        initial_project_name,
    )

    scenarios = data_handler.scenarios
    years = data_handler.years
    available_projects_ = available_projects or []

    # Discover available projects if not provided
    if not available_projects_:
        recent = get_recent_projects()
        seen_ids: set[str] = set()

        for proj in recent:
            project_id = proj["project_id"]
            path = Path(proj["path"]).resolve()
            if project_id not in seen_ids and path.exists():
                available_projects_.append(proj)
                seen_ids.add(project_id)

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

    # Get current project display name
    current_project_name = data_handler.project.config.project_id

    # Build dropdown options with deduplication by project_id
    dropdown_options = [{"label": current_project_name, "value": current_project_path}]
    seen_project_ids = {current_project_name}
    for p in available_projects_:
        project_id = p.get("project_id", "")
        if project_id and project_id not in seen_project_ids:
            dropdown_options.append(
                {"label": p.get("name", "Unknown"), "value": p.get("path", "")}
            )
            seen_project_ids.add(project_id)

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
                            html.H6("Project", className="text-white-50 mb-2"),
                            # Current project display
                            html.Div(
                                current_project_name,
                                id="current-project-name",
                                className="mb-2 p-2 rounded project-name-display",
                                style={"fontSize": "0.95rem"},
                            ),
                            # Current project path (read-only)
                            dcc.Input(
                                id="current-project-path-display",
                                value=current_project_path,
                                type="text",
                                readOnly=True,
                                className="form-control form-control-sm mb-2",
                                style={
                                    "fontSize": "0.75rem",
                                    "backgroundColor": "#2a2a2a",
                                    "color": "#888",
                                    "border": "1px solid #444",
                                },
                            ),
                            # Text input for new path (before dropdown for tab order)
                            dcc.Input(
                                id="project-path-input",
                                placeholder="Enter project path...",
                                type="text",
                                className="form-control form-control-sm mb-2",
                                autoComplete="off",
                                spellCheck=False,
                                debounce=True,  # Only update on Enter or blur
                            ),
                            # Load button
                            dbc.Button(
                                [html.I(className="bi bi-folder-plus me-2"), "Load Project"],
                                id="load-project-btn",
                                color="primary",
                                size="sm",
                                className="mb-2 w-100",
                            ),
                            # Status message
                            html.Div(
                                id="project-load-status",
                                className="small mb-2",
                                style={"fontSize": "0.8rem"},
                            ),
                            # Dropdown for available projects (recent + discovered)
                            dcc.Dropdown(
                                id="project-switcher-dropdown",
                                options=dropdown_options,  # type: ignore[arg-type]
                                value=current_project_path,
                                placeholder="Switch project...",
                                className="mb-2",
                                style={"fontSize": "0.85rem"},
                                clearable=False,
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
            cached_project, _, _, project_name = _loaded_projects[_current_project_path]

            # Create a copy of the palette to avoid modifying the original
            palette_copy = palette.copy()

            # Get current data handler (singleton)
            data_handler = APIClient(cached_project)

            # Create fresh color manager with new palette
            color_manager = create_fresh_color_manager(palette_copy, data_handler.scenarios)

            plotter = StridePlots(color_manager, template="plotly_dark")

            # Update cache (preserve project and project_name)
            _loaded_projects[_current_project_path] = (
                cached_project,
                color_manager,
                plotter,
                project_name,
            )

            logger.info(f"Palette changed to: {palette_type} / {palette_name}")

    # Helper function to get color manager
    def get_current_color_manager() -> ColorManager | None:
        """Get the current color manager instance."""
        if _current_project_path in _loaded_projects:
            _, color_manager, _, _ = _loaded_projects[_current_project_path]
            return color_manager
        return None

    # Helper function to get data handler
    def get_current_data_handler() -> "APIClient | None":
        """Get the current data handler instance (APIClient singleton)."""
        if _current_project_path in _loaded_projects:
            cached_project, _, _, _ = _loaded_projects[_current_project_path]
            # Ensure singleton is pointing to correct project and return it
            return APIClient(cached_project)
        return None

    # Helper function to get plotter
    def get_current_plotter() -> "StridePlots | None":
        """Get the current plotter instance."""
        if _current_project_path in _loaded_projects:
            _, _, plotter, _ = _loaded_projects[_current_project_path]
            return plotter
        return None

    # Register callbacks
    register_home_callbacks(
        get_current_data_handler,
        get_current_plotter,
        scenarios,
        literal_to_list(Sectors),
        years,
        get_current_color_manager,
    )

    register_scenario_callbacks(get_current_data_handler, get_current_plotter)

    register_settings_callbacks(
        get_current_data_handler,
        get_current_color_manager,
        on_palette_change,
    )

    # Callback to update scenario CSS when palette changes
    @callback(
        Output("scenario-css-container", "children"),
        Input("settings-palette-applied", "data"),
        Input("color-edits-counter", "data"),
    )
    def update_scenario_css(palette_data: dict[str, Any], color_edits: int) -> list[Any]:
        """Update scenario CSS when palette changes or colors are edited."""
        color_manager = get_current_color_manager()
        if color_manager is None:
            raise PreventUpdate

        # Get temporary color edits to apply to CSS
        temp_edits = get_temp_color_edits()

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
                    style.textContent = `{color_manager.generate_scenario_css(temp_edits)}`;
                    document.head.appendChild(style);
                }})();
                """
            )
        ]

    # Project switching callback
    @callback(
        Output("current-project-path", "data"),
        Output("project-load-status", "children"),
        Output("current-project-name", "children"),
        Output("current-project-path-display", "value"),
        Output("project-switcher-dropdown", "options"),
        Output("project-switcher-dropdown", "value"),
        Input("load-project-btn", "n_clicks"),
        Input("project-path-input", "n_submit"),  # Trigger on Enter key
        Input("project-switcher-dropdown", "value"),
        State("project-path-input", "value"),
        State("current-project-path", "data"),
        State("project-switcher-dropdown", "options"),
        prevent_initial_call=True,
    )
    def handle_project_switch(
        load_clicks: int | None,
        n_submit: int | None,
        dropdown_value: str | None,
        path_input: str | None,
        current_path: str,
        current_options: list[dict[str, str]],
    ) -> tuple[Any, ...]:
        """Handle project loading and switching."""
        from dash import ctx, no_update

        global _current_project_path

        trigger_id = ctx.triggered_id if ctx.triggered_id else None

        # Handle load button click OR Enter key in path input
        if trigger_id in ("load-project-btn", "project-path-input") and path_input:
            success, message = load_project(path_input)
            if success:
                data_handler = get_current_data_handler()
                project_name = (
                    data_handler.project.config.project_id if data_handler else "Unknown"
                )
                # Add new project to dropdown if not already there
                existing_paths = {opt.get("value") for opt in current_options}
                new_options: Any
                if _current_project_path not in existing_paths:
                    new_options = [
                        {"label": project_name, "value": _current_project_path},
                        *current_options,
                    ]
                else:
                    new_options = no_update
                return (
                    _current_project_path,
                    html.Span(message, className="text-success"),
                    project_name,
                    _current_project_path,
                    new_options,
                    _current_project_path,
                )
            else:
                return (
                    no_update,
                    html.Span(message, className="text-danger"),
                    no_update,
                    no_update,
                    no_update,
                    no_update,
                )

        elif trigger_id == "project-switcher-dropdown" and dropdown_value:
            # Switch to selected project from dropdown
            if dropdown_value != current_path:
                if dropdown_value in _loaded_projects:
                    # Project already loaded - just switch to it
                    _current_project_path = dropdown_value
                    cached_project, _, _, project_name = _loaded_projects[dropdown_value]
                    # Update the APIClient singleton to point to this project
                    APIClient(cached_project)
                    return (
                        dropdown_value,
                        html.Span(f"Switched to {project_name}", className="text-success"),
                        project_name,
                        dropdown_value,
                        no_update,
                        dropdown_value,
                    )
                else:
                    # Project not yet loaded - load it (handles recent projects)
                    success, message = load_project(dropdown_value)
                    if success:
                        data_handler = get_current_data_handler()
                        project_name = (
                            data_handler.project.config.project_id if data_handler else "Unknown"
                        )
                        return (
                            _current_project_path,
                            html.Span(message, className="text-success"),
                            project_name,
                            _current_project_path,
                            no_update,  # Don't replace dropdown options
                            _current_project_path,
                        )
                    else:
                        return (
                            no_update,
                            html.Span(message, className="text-danger"),
                            no_update,
                            no_update,
                            no_update,
                            current_path,  # Reset dropdown to current project
                        )

        raise PreventUpdate

    # Update navigation tabs when project changes
    @callback(
        Output("view-selector", "options"),
        Output("view-selector", "value", allow_duplicate=True),
        Input("current-project-path", "data"),
        prevent_initial_call=True,
    )
    def update_navigation_tabs(project_path: str) -> tuple[list[dict[str, str]], str]:
        """Update navigation tabs when project changes."""
        data_handler = get_current_data_handler()
        if data_handler is None:
            return [{"label": "Home", "value": "compare"}], "compare"

        new_scenarios = data_handler.scenarios
        options = [
            {"label": "Home", "value": "compare"},
            *[{"label": s, "value": s} for s in new_scenarios],
        ]
        return options, "compare"  # Reset to home view

    # Regenerate home layout when project changes
    @callback(
        Output("home-view", "children"),
        Input("current-project-path", "data"),
        prevent_initial_call=True,
    )
    def regenerate_home_layout(project_path: str) -> list[Any]:
        """Regenerate home layout when project changes."""
        data_handler = get_current_data_handler()
        color_manager = get_current_color_manager()
        if data_handler is None or color_manager is None:
            return [html.Div("No project loaded")]

        new_scenarios = data_handler.scenarios
        new_years = data_handler.years
        return [create_home_layout(new_scenarios, new_years, color_manager)]

    # Regenerate scenario layout when project changes
    @callback(
        Output("scenario-view", "children"),
        Input("current-project-path", "data"),
        prevent_initial_call=True,
    )
    def regenerate_scenario_layout(project_path: str) -> list[Any]:
        """Regenerate scenario layout when project changes."""
        data_handler = get_current_data_handler()
        color_manager = get_current_color_manager()
        if data_handler is None or color_manager is None:
            return [html.Div("No project loaded")]

        new_years = data_handler.years
        return [create_scenario_layout(new_years, color_manager)]

    # Update scenario CSS when project changes
    @callback(
        Output("scenario-css-container", "children", allow_duplicate=True),
        Input("current-project-path", "data"),
        prevent_initial_call=True,
    )
    def update_scenario_css_on_project_change(project_path: str) -> list[Any]:
        """Update scenario CSS when project changes."""
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


def create_app_no_project(
    user_palette: ColorPalette | None = None,
) -> Dash:
    """
    Create the Dash application without a project loaded.

    This allows users to start the UI and load a project via the sidebar.

    Parameters
    ----------
    user_palette : ColorPalette | None, optional
        User palette to use as default when a project is loaded

    Returns
    -------
    Dash
        Configured Dash application
    """
    global _loaded_projects, _current_project_path

    # Reset global state
    _loaded_projects = {}
    _current_project_path = None

    # Create a default color manager with minimal settings
    default_palette = user_palette or ColorPalette()
    color_manager = create_fresh_color_manager(default_palette, [])

    # Get recent projects for the dropdown
    available_projects_: list[dict[str, Any]] = []
    recent = get_recent_projects()
    seen_ids: set[str] = set()

    for proj in recent:
        project_id = proj["project_id"]
        path = Path(proj["path"]).resolve()
        if project_id not in seen_ids and path.exists():
            available_projects_.append(proj)
            seen_ids.add(project_id)

    # Build dropdown options from recent projects only
    dropdown_options = []
    for p in available_projects_:
        project_id = p.get("project_id", "")
        if project_id:
            dropdown_options.append(
                {"label": p.get("name", project_id), "value": p.get("path", "")}
            )

    # Create the welcome message for no-project state
    no_project_message = html.Div(
        [
            html.Div(
                [
                    html.H2("Welcome to STRIDE", className="text-center mb-4"),
                    html.P(
                        "No project is currently loaded.",
                        className="text-center text-muted mb-4",
                    ),
                    html.Hr(),
                    html.H5("To get started:", className="mb-3"),
                    html.Ol(
                        [
                            html.Li(
                                [
                                    "Click the ",
                                    html.Strong("›"),
                                    " button in the top-left corner to open the sidebar",
                                ],
                                className="mb-2",
                            ),
                            html.Li(
                                [
                                    "Enter a project path in the ",
                                    html.Strong("Enter project path..."),
                                    " field",
                                ],
                                className="mb-2",
                            ),
                            html.Li(
                                [
                                    "Click ",
                                    html.Strong("Load Project"),
                                    " to load your project",
                                ],
                                className="mb-2",
                            ),
                        ],
                        className="mb-4",
                    ),
                    html.P(
                        [
                            "Or select a recent project from the dropdown if available.",
                        ],
                        className="text-muted",
                    ),
                    html.Hr(),
                    html.P(
                        [
                            "To create a new project, use the CLI: ",
                            html.Code("stride projects create <config.json5>"),
                        ],
                        className="text-muted small",
                    ),
                ],
                className="p-5",
                style={
                    "maxWidth": "600px",
                    "margin": "100px auto",
                    "backgroundColor": "#1e1e1e",
                    "borderRadius": "10px",
                    "border": "1px solid #333",
                },
            ),
        ],
        id="no-project-welcome",
    )

    # Create sidebar (similar to create_app but without project-specific data)
    sidebar = html.Div(
        [
            html.Div(
                [
                    html.H4("Navigation", className="text-white mb-4"),
                    html.Hr(className="bg-white"),
                    # Projects section
                    html.Div(
                        [
                            html.H6("Project", className="text-white-50 mb-2"),
                            # Current project display
                            html.Div(
                                "No project loaded",
                                id="current-project-name",
                                className="mb-2 p-2 rounded project-name-display",
                                style={"fontSize": "0.95rem"},
                            ),
                            # Current project path (read-only)
                            dcc.Input(
                                id="current-project-path-display",
                                value="",
                                type="text",
                                readOnly=True,
                                className="form-control form-control-sm mb-2",
                                style={
                                    "fontSize": "0.75rem",
                                    "backgroundColor": "#2a2a2a",
                                    "color": "#888",
                                    "border": "1px solid #444",
                                },
                            ),
                            # Text input for new path
                            dcc.Input(
                                id="project-path-input",
                                placeholder="Enter project path...",
                                type="text",
                                className="form-control form-control-sm mb-2",
                                autoComplete="off",
                                spellCheck=False,
                                debounce=True,
                            ),
                            # Load button
                            dbc.Button(
                                [html.I(className="bi bi-folder-plus me-2"), "Load Project"],
                                id="load-project-btn",
                                color="primary",
                                size="sm",
                                className="mb-2 w-100",
                            ),
                            # Status message
                            html.Div(
                                id="project-load-status",
                                className="small mb-2",
                                style={"fontSize": "0.8rem"},
                            ),
                            # Dropdown for available projects (recent only)
                            dcc.Dropdown(
                                id="project-switcher-dropdown",
                                options=dropdown_options,  # type: ignore[arg-type]
                                value=None,
                                placeholder="Select a recent project...",
                                className="mb-2",
                                style={"fontSize": "0.85rem"},
                                clearable=True,
                            ),
                        ]
                    ),
                    html.Hr(className="bg-white"),
                    # Settings link (disabled without project)
                    html.Div(
                        [
                            dbc.Button(
                                [html.I(className="bi bi-gear me-2"), "Settings"],
                                id="sidebar-settings-btn",
                                color="light",
                                outline=True,
                                className="w-100",
                                disabled=True,
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
            dcc.Store(id="settings-palette-applied", data={"type": "default", "name": None}),
            dcc.Store(id="current-project-path", data=""),
            dcc.Store(id="sidebar-open", data=False),
            dcc.Store(id="chart-refresh-trigger", data=0),
            dcc.Store(id="theme-store", data="dark"),
            # Empty scenario CSS container
            html.Div(id="scenario-css-container", children=[], style={"display": "none"}),
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
                                ],
                            ),
                        ],
                        className="header-bar",
                    ),
                    # Navigation tabs (hidden until project loaded)
                    html.Div(
                        [
                            dbc.RadioItems(
                                id="view-selector",
                                className="nav-tabs-custom",
                                options=[{"label": "Home", "value": "compare"}],
                                value="compare",
                                inline=True,
                            ),
                        ],
                        className="nav-container",
                        style={"display": "none"},
                        id="nav-container",
                    ),
                    # Content area - show welcome message
                    html.Div(
                        [
                            html.Div(no_project_message, id="home-view"),
                            html.Div(id="scenario-view", style={"display": "none"}),
                            html.Div(id="settings-view", style={"display": "none"}),
                        ],
                        id="content-area",
                        style={"padding": "20px"},
                    ),
                ],
                id="main-content",
                style={
                    "marginLeft": "0",
                    "transition": "margin-left 0.3s ease-in-out",
                },
            ),
        ],
        className="dark-theme",
    )

    # Register callbacks for no-project mode
    _register_no_project_callbacks(app, color_manager, dropdown_options)

    return app


def _register_no_project_callbacks(
    app: Dash,
    initial_color_manager: ColorManager,
    initial_dropdown_options: list[dict[str, str]],
) -> None:
    """Register callbacks for the no-project app mode."""
    from dash import ctx, no_update

    # Helper function to get current data handler
    def get_current_data_handler() -> "APIClient | None":
        """Get the current API client instance."""
        if _current_project_path and _current_project_path in _loaded_projects:
            cached_project, _, _, _ = _loaded_projects[_current_project_path]
            # Return the APIClient singleton (which should be updated to use this project)
            try:
                return APIClient(cached_project)
            except Exception:
                return None
        return None

    # Helper function to get current color manager
    def get_current_color_manager() -> "ColorManager | None":
        """Get the current color manager instance."""
        if _current_project_path and _current_project_path in _loaded_projects:
            _, color_manager, _, _ = _loaded_projects[_current_project_path]
            return color_manager
        return initial_color_manager

    # Sidebar toggle callback
    @callback(
        Output("sidebar", "style"),
        Output("main-content", "style"),
        Output("sidebar-open", "data"),
        Input("sidebar-toggle", "n_clicks"),
        State("sidebar-open", "data"),
        prevent_initial_call=True,
    )
    def toggle_sidebar(n_clicks: int | None, is_open: bool) -> tuple[dict[str, Any], dict[str, Any], bool]:
        """Toggle the sidebar visibility."""
        if is_open:
            return (
                {
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
                {"marginLeft": "0", "transition": "margin-left 0.3s ease-in-out"},
                False,
            )
        else:
            return (
                {
                    "position": "fixed",
                    "top": 0,
                    "left": 0,
                    "bottom": 0,
                    "width": "250px",
                    "zIndex": 1000,
                    "transform": "translateX(0)",
                    "transition": "transform 0.3s ease-in-out",
                    "overflowY": "auto",
                },
                {"marginLeft": "250px", "transition": "margin-left 0.3s ease-in-out"},
                True,
            )

    # Project loading callback
    @callback(
        Output("current-project-path", "data"),
        Output("project-load-status", "children"),
        Output("current-project-name", "children"),
        Output("current-project-path-display", "value"),
        Output("project-switcher-dropdown", "options"),
        Output("project-switcher-dropdown", "value"),
        Output("home-view", "children"),
        Output("nav-container", "style"),
        Output("sidebar-settings-btn", "disabled"),
        Input("load-project-btn", "n_clicks"),
        Input("project-path-input", "n_submit"),
        Input("project-switcher-dropdown", "value"),
        State("project-path-input", "value"),
        State("current-project-path", "data"),
        State("project-switcher-dropdown", "options"),
        prevent_initial_call=True,
    )
    def handle_project_load(
        load_clicks: int | None,
        n_submit: int | None,
        dropdown_value: str | None,
        path_input: str | None,
        current_path: str,
        current_options: list[dict[str, str]],
    ) -> tuple[Any, ...]:
        """Handle project loading."""
        global _current_project_path

        trigger_id = ctx.triggered_id if ctx.triggered_id else None
        path_to_load = None

        if trigger_id in ("load-project-btn", "project-path-input") and path_input:
            path_to_load = path_input
        elif trigger_id == "project-switcher-dropdown" and dropdown_value:
            path_to_load = dropdown_value

        if path_to_load:
            success, message = load_project(path_to_load)
            if success:
                data_handler = get_current_data_handler()
                color_manager = get_current_color_manager()
                if data_handler and color_manager:
                    project_name = data_handler.project.config.project_id
                    new_scenarios = data_handler.scenarios
                    new_years = data_handler.years

                    # Add to dropdown if not there
                    existing_paths = {opt.get("value") for opt in current_options}
                    if _current_project_path not in existing_paths:
                        new_options = [
                            {"label": project_name, "value": _current_project_path},
                            *current_options,
                        ]
                    else:
                        new_options = current_options

                    # Create home layout for the loaded project
                    new_home_layout = create_home_layout(new_scenarios, new_years, color_manager)

                    return (
                        _current_project_path,
                        html.Span(message, className="text-success"),
                        project_name,
                        _current_project_path,
                        new_options,
                        _current_project_path,
                        new_home_layout,
                        {"display": "block"},  # Show nav container
                        False,  # Enable settings button
                    )
            return (
                no_update,
                html.Span(message, className="text-danger"),
                no_update,
                no_update,
                no_update,
                no_update,
                no_update,
                no_update,
                no_update,
            )

        raise PreventUpdate

    # View selector callback
    @callback(
        Output("home-view", "style"),
        Output("scenario-view", "style"),
        Output("scenario-view", "children", allow_duplicate=True),
        Output("view-selector", "options", allow_duplicate=True),
        Input("view-selector", "value"),
        State("current-project-path", "data"),
        prevent_initial_call=True,
    )
    def switch_view(view: str, project_path: str) -> tuple[Any, ...]:
        """Switch between views."""
        if not project_path:
            raise PreventUpdate

        data_handler = get_current_data_handler()
        color_manager = get_current_color_manager()
        if data_handler is None or color_manager is None:
            raise PreventUpdate

        scenarios = data_handler.scenarios
        years = data_handler.years
        options = [
            {"label": "Home", "value": "compare"},
            *[{"label": s, "value": s} for s in scenarios],
        ]

        if view == "compare":
            return (
                {"display": "block"},
                {"display": "none"},
                no_update,
                options,
            )
        else:
            # Scenario view
            scenario_layout = create_scenario_layout(years, color_manager)
            return (
                {"display": "none"},
                {"display": "block"},
                scenario_layout,
                options,
            )

    # Helper function to get plotter
    def get_current_plotter() -> "StridePlots | None":
        """Get the current plotter instance."""
        if _current_project_path and _current_project_path in _loaded_projects:
            _, _, plotter, _ = _loaded_projects[_current_project_path]
            return plotter
        return None

    # Register home and scenario callbacks with dynamic data fetching
    # These will use the helper functions to get the current project data
    register_home_callbacks(
        get_current_data_handler,
        get_current_plotter,
        [],  # Initial empty scenarios - will be populated when project loads
        literal_to_list(Sectors),
        [],  # Initial empty years - will be populated when project loads
        get_current_color_manager,
    )

    register_scenario_callbacks(get_current_data_handler, get_current_plotter)