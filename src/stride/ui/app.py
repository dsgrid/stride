from __future__ import annotations

from pathlib import Path
from typing import Any

import dash_bootstrap_components as dbc
from dash import Dash, Input, Output, State, callback, ctx, dcc, html, no_update
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

# ============================================================================
# Shared styles and constants
# ============================================================================

SIDEBAR_STYLE_CLOSED: dict[str, Any] = {
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

SIDEBAR_STYLE_OPEN: dict[str, Any] = {
    "position": "fixed",
    "top": 0,
    "left": 0,
    "bottom": 0,
    "width": "250px",
    "zIndex": 1000,
    "transform": "translateX(0)",
    "transition": "transform 0.3s ease-in-out",
    "overflowY": "auto",
}

CONTENT_STYLE_SIDEBAR_CLOSED: dict[str, Any] = {
    "marginLeft": "0",
    "transition": "margin-left 0.3s ease-in-out",
}

CONTENT_STYLE_SIDEBAR_OPEN: dict[str, Any] = {
    "marginLeft": "250px",
    "transition": "margin-left 0.3s ease-in-out",
}


# Global state for loaded projects
# project_path -> (project, color_manager, plotter, project_name)
# Note: We store Project instead of APIClient because APIClient is a singleton
_loaded_projects: dict[str, tuple[Project, ColorManager, StridePlots, str]] = {}
_current_project_path: str | None = None


# ============================================================================
# Shared layout components
# ============================================================================


def _create_sidebar(
    current_project_name: str,
    current_project_path: str,
    dropdown_options: list[dict[str, str]],
    dropdown_value: str | None,
    dropdown_placeholder: str = "Switch project...",
    settings_disabled: bool = False,
    dropdown_clearable: bool = False,
) -> html.Div:
    """Create the sidebar component.

    Parameters
    ----------
    current_project_name : str
        Display name for the current project (or "No project loaded")
    current_project_path : str
        Path to display for the current project (or empty string)
    dropdown_options : list[dict[str, str]]
        Options for the project dropdown
    dropdown_value : str | None
        Currently selected value in the dropdown
    dropdown_placeholder : str
        Placeholder text for the dropdown
    settings_disabled : bool
        Whether the settings button should be disabled
    dropdown_clearable : bool
        Whether the dropdown should be clearable

    Returns
    -------
    html.Div
        The sidebar component
    """
    return html.Div(
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
                            # Dropdown for available projects
                            dcc.Dropdown(
                                id="project-switcher-dropdown",
                                options=dropdown_options,  # type: ignore[arg-type]
                                value=dropdown_value,
                                placeholder=dropdown_placeholder,
                                className="mb-2",
                                style={"fontSize": "0.85rem"},
                                clearable=dropdown_clearable,
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
                                disabled=settings_disabled,
                            ),
                        ]
                    ),
                ],
                className="p-3",
            ),
        ],
        id="sidebar",
        className="sidebar-nav dark-theme",
        style=SIDEBAR_STYLE_CLOSED,
    )


def _create_header() -> html.Div:
    """Create the header component with sidebar toggle and theme toggle.

    Returns
    -------
    html.Div
        The header component
    """
    return html.Div(
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
        className="header-bar",
    )


def _create_state_stores(
    current_project_path: str,
    current_palette_type: str = "project",
    current_palette_name: str | None = None,
) -> list[dcc.Store]:
    """Create the state store components.

    Parameters
    ----------
    current_project_path : str
        Path to the current project (or empty string)
    current_palette_type : str
        Type of palette ("project", "user", or "default")
    current_palette_name : str | None
        Name of the palette if user type

    Returns
    -------
    list[dcc.Store]
        List of store components
    """
    # Note: color-edits-counter is created in settings/layout.py
    return [
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
    ]


def _create_nav_tabs(
    scenarios: list[str],
    hidden: bool = False,
) -> html.Div:
    """Create the navigation tabs component.

    Parameters
    ----------
    scenarios : list[str]
        List of scenario names
    hidden : bool
        Whether to hide the nav tabs initially

    Returns
    -------
    html.Div
        The navigation tabs component
    """
    options = [
        {"label": "Home", "value": "compare"},
        *[{"label": s, "value": s} for s in scenarios],
    ]
    return html.Div(
        [
            dbc.RadioItems(
                id="view-selector",
                className="btn-group",
                inputClassName="btn-check",
                labelClassName="btn btn-outline-primary",
                labelCheckedClassName="active",
                options=options,
                value="compare",
            )
        ],
        className="nav-tabs",
        id="nav-tabs-container",
        style={"display": "none"} if hidden else {"display": "block"},
    )


def _create_scenario_css_container(
    color_manager: ColorManager | None = None,
) -> html.Div:
    """Create the scenario CSS container.

    Parameters
    ----------
    color_manager : ColorManager | None
        Color manager to generate CSS from, or None for empty container

    Returns
    -------
    html.Div
        The scenario CSS container
    """
    if color_manager is None:
        children: list[Any] = []
    else:
        children = _generate_scenario_css_script(color_manager)

    return html.Div(
        id="scenario-css-container",
        children=children,
        style={"display": "none"},
    )


def _generate_scenario_css_script(
    color_manager: ColorManager,
    temp_edits: dict[str, str] | None = None,
) -> list[Any]:
    """Generate the scenario CSS script element.

    Parameters
    ----------
    color_manager : ColorManager
        Color manager to generate CSS from
    temp_edits : dict[str, str] | None
        Optional temporary color edits to apply

    Returns
    -------
    list[Any]
        List containing the script element
    """
    css_content = (
        color_manager.generate_scenario_css(temp_edits)
        if temp_edits
        else color_manager.generate_scenario_css()
    )
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
                style.textContent = `{css_content}`;
                document.head.appendChild(style);
            }})();
            """
        )
    ]


def _create_welcome_message() -> html.Div:
    """Create the welcome message for no-project state.

    Returns
    -------
    html.Div
        The welcome message component
    """
    return html.Div(
        [
            html.Div(
                [
                    html.H2("Welcome to STRIDE", className="text-center mb-4 welcome-title"),
                    html.P(
                        "No project is currently loaded.",
                        className="text-center text-muted mb-4",
                    ),
                    html.Hr(className="welcome-hr"),
                    html.H5("To get started:", className="mb-3 welcome-subtitle"),
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
                        className="mb-4 welcome-list",
                    ),
                    html.P(
                        [
                            "Or select a recent project from the dropdown if available.",
                        ],
                        className="text-muted",
                    ),
                    html.Hr(className="welcome-hr"),
                    html.P(
                        [
                            "To create a new project, use the CLI: ",
                            html.Code(
                                "stride projects create <config.json5>", className="welcome-code"
                            ),
                        ],
                        className="text-muted small",
                    ),
                ],
                className="p-5 welcome-box",
                style={
                    "maxWidth": "600px",
                    "margin": "100px auto",
                    "borderRadius": "10px",
                },
            ),
        ],
        id="no-project-welcome",
    )


def _get_recent_project_options() -> list[dict[str, Any]]:
    """Get recent projects as dropdown options.

    Returns
    -------
    list[dict[str, Any]]
        List of recent project options
    """
    available_projects: list[dict[str, Any]] = []
    recent = get_recent_projects()
    seen_ids: set[str] = set()

    for proj in recent:
        project_id = proj["project_id"]
        path = Path(proj["path"]).resolve()
        if project_id not in seen_ids and path.exists():
            available_projects.append(proj)
            seen_ids.add(project_id)

    return available_projects


# ============================================================================
# Shared helper functions for accessing global state
# ============================================================================


def _get_current_data_handler() -> APIClient | None:
    """Get the current API client instance from global state."""
    if _current_project_path and _current_project_path in _loaded_projects:
        cached_project, _, _, _ = _loaded_projects[_current_project_path]
        try:
            return APIClient(cached_project)
        except Exception:
            return None
    return None


def _get_current_color_manager() -> ColorManager | None:
    """Get the current color manager instance from global state."""
    if _current_project_path and _current_project_path in _loaded_projects:
        _, color_manager, _, _ = _loaded_projects[_current_project_path]
        return color_manager
    return None


def _get_current_plotter() -> StridePlots | None:
    """Get the current plotter instance from global state."""
    if _current_project_path and _current_project_path in _loaded_projects:
        _, _, plotter, _ = _loaded_projects[_current_project_path]
        return plotter
    return None


def _on_palette_change(
    palette: ColorPalette,
    palette_type: str,
    palette_name: str | None,
) -> None:
    """Update the color manager when palette changes."""
    global _loaded_projects, _current_project_path

    if _current_project_path and _current_project_path in _loaded_projects:
        cached_project, _, _, project_name = _loaded_projects[_current_project_path]

        palette_copy = palette.copy()
        data_handler = APIClient(cached_project)
        new_color_manager = create_fresh_color_manager(palette_copy, data_handler.scenarios)
        new_plotter = StridePlots(new_color_manager, template="plotly_dark")

        _loaded_projects[_current_project_path] = (
            cached_project,
            new_color_manager,
            new_plotter,
            project_name,
        )

        logger.info(f"Palette changed to: {palette_type} / {palette_name}")


# ============================================================================
# Core functions
# ============================================================================


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


def create_app(
    data_handler: APIClient,
    user_palette: ColorPalette | None = None,
    available_projects: list[dict[str, str]] | None = None,
) -> Dash:
    """Create the Dash application with a project loaded.

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

    # Store in global cache
    initial_project_name = data_handler.project.config.project_id
    initial_project = data_handler.project
    _loaded_projects[current_project_path] = (
        initial_project,
        color_manager,
        plotter,
        initial_project_name,
    )

    scenarios = data_handler.scenarios
    years = data_handler.years

    # Discover available projects if not provided
    available_projects_ = available_projects or []
    if not available_projects_:
        available_projects_ = _get_recent_project_options()

    # Add current project to recent projects
    try:
        add_recent_project(
            data_handler.project.path,
            data_handler.project.config.project_id,
        )
    except Exception as e:
        logger.warning(f"Could not add to recent projects: {e}")

    # Create layouts
    home_layout = create_home_layout(scenarios, years, color_manager)
    scenario_layout = create_scenario_layout(years, color_manager)

    # Create settings layout
    try:
        user_palettes_paths = list_user_palettes()
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

    # Build dropdown options with deduplication
    current_project_name = data_handler.project.config.project_id
    dropdown_options = [{"label": current_project_name, "value": current_project_path}]
    seen_project_ids = {current_project_name}
    for p in available_projects_:
        project_id = p.get("project_id", "")
        if project_id and project_id not in seen_project_ids:
            dropdown_options.append(
                {"label": p.get("name", "Unknown"), "value": p.get("path", "")}
            )
            seen_project_ids.add(project_id)

    # Create layout using shared components
    sidebar = _create_sidebar(
        current_project_name=current_project_name,
        current_project_path=current_project_path,
        dropdown_options=dropdown_options,
        dropdown_value=current_project_path,
        dropdown_placeholder="Switch project...",
        settings_disabled=False,
        dropdown_clearable=False,
    )

    app.layout = html.Div(
        [
            *_create_state_stores(
                current_project_path=current_project_path,
                current_palette_type=current_palette_type,
                current_palette_name=current_palette_name,
            ),
            _create_scenario_css_container(color_manager),
            sidebar,
            html.Div(
                [
                    _create_header(),
                    _create_nav_tabs(scenarios, hidden=False),
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
                style=CONTENT_STYLE_SIDEBAR_CLOSED,
            ),
        ],
        className="dark-theme",
        style={"minHeight": "100vh"},
    )

    # Register callbacks
    _register_common_callbacks()
    _register_project_callbacks()

    register_home_callbacks(
        _get_current_data_handler,
        _get_current_plotter,
        scenarios,
        literal_to_list(Sectors),
        years,
        _get_current_color_manager,
    )

    register_scenario_callbacks(_get_current_data_handler, _get_current_plotter)

    register_settings_callbacks(
        _get_current_data_handler,
        _get_current_color_manager,
        _on_palette_change,
    )

    return app


# ============================================================================
# Shared callback registration
# ============================================================================


def _register_common_callbacks() -> None:  # noqa: C901
    """Register callbacks common to both app modes (with and without project)."""

    @callback(
        Output("sidebar", "style"),
        Output("page-content", "style"),
        Output("sidebar-open", "data"),
        Output("sidebar-toggle", "children"),
        Input("sidebar-toggle", "n_clicks"),
        State("sidebar-open", "data"),
        prevent_initial_call=True,
    )
    def toggle_sidebar(
        n_clicks: int | None,
        is_open: bool,
    ) -> tuple[dict[str, Any], dict[str, Any], bool, html.Span]:
        """Toggle sidebar visibility."""
        if n_clicks is None:
            return (
                {},
                {},
                is_open,
                html.Span("›", style={"fontSize": "1.5rem", "fontWeight": "bold"}),
            )

        new_state = not is_open
        button_icon = (
            html.Span("‹", style={"fontSize": "1.5rem", "fontWeight": "bold"})
            if new_state
            else html.Span("›", style={"fontSize": "1.5rem", "fontWeight": "bold"})
        )

        if new_state:
            return SIDEBAR_STYLE_OPEN, CONTENT_STYLE_SIDEBAR_OPEN, True, button_icon
        return SIDEBAR_STYLE_CLOSED, CONTENT_STYLE_SIDEBAR_CLOSED, False, button_icon

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

        plotter = _get_current_plotter()
        if plotter:
            template = "plotly_dark" if is_dark else "plotly_white"
            plotter.set_template(template)
            logger.info(f"Switched to {theme} with plot template {template}")

        return f"page-content {theme}", f"sidebar-nav {theme}", theme, refresh_count + 1

    @callback(
        Output("home-view", "hidden"),
        Output("scenario-view", "hidden"),
        Output("settings-view", "hidden"),
        Output("nav-tabs-container", "style"),
        Output("view-selector", "value"),
        Output("chart-refresh-trigger", "data"),
        Output("scenario-view", "children", allow_duplicate=True),
        Input("view-selector", "value"),
        Input("sidebar-settings-btn", "n_clicks"),
        Input("back-to-dashboard-btn", "n_clicks"),
        Input("home-link", "n_clicks"),
        State("settings-view", "hidden"),
        State("chart-refresh-trigger", "data"),
        State("current-project-path", "data"),
        prevent_initial_call="initial_duplicate",
    )
    def toggle_views(
        selected_view: str,
        settings_clicks: int | None,
        back_clicks: int | None,
        home_clicks: int | None,
        settings_hidden: bool,
        current_refresh_count: int,
        project_path: str,
    ) -> tuple[bool, bool, bool, dict[str, str], str, int, Any]:
        """Toggle between home, scenario, and settings views."""
        trigger_id = ctx.triggered_id if ctx.triggered_id else None

        # For no-project mode, prevent updates if no project loaded (except for specific triggers)
        if not project_path and trigger_id not in ("sidebar-settings-btn",):
            raise PreventUpdate

        if trigger_id == "sidebar-settings-btn":
            if not project_path:
                raise PreventUpdate
            return (
                True,
                True,
                False,
                {"display": "none"},
                selected_view,
                current_refresh_count,
                no_update,
            )

        if trigger_id in ("back-to-dashboard-btn", "home-link"):
            temp_edits = get_temp_color_edits()
            if temp_edits:
                color_manager = _get_current_color_manager()
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
                no_update,
            )

        if selected_view == "compare":
            return (
                False,
                True,
                True,
                {"display": "block"},
                selected_view,
                current_refresh_count,
                no_update,
            )

        # Scenario view - need to create layout
        data_handler = _get_current_data_handler()
        color_manager = _get_current_color_manager()
        if data_handler is None or color_manager is None:
            raise PreventUpdate

        scenario_layout = create_scenario_layout(data_handler.years, color_manager)
        return (
            True,
            False,
            True,
            {"display": "block"},
            selected_view,
            current_refresh_count,
            scenario_layout,
        )

    @callback(
        Output("scenario-css-container", "children"),
        Input("settings-palette-applied", "data"),
        Input("color-edits-counter", "data"),
        State("current-project-path", "data"),
        prevent_initial_call=True,
    )
    def update_scenario_css(
        palette_data: dict[str, Any],
        color_edits: int,
        project_path: str,
    ) -> list[Any]:
        """Update scenario CSS when palette changes or colors are edited."""
        if not project_path:
            raise PreventUpdate

        color_manager = _get_current_color_manager()
        if color_manager is None:
            raise PreventUpdate

        temp_edits = get_temp_color_edits()
        return _generate_scenario_css_script(color_manager, temp_edits)


def _register_project_callbacks() -> None:
    """Register callbacks for project switching (used in both modes)."""

    @callback(
        Output("current-project-path", "data"),
        Output("project-load-status", "children"),
        Output("current-project-name", "children"),
        Output("current-project-path-display", "value"),
        Output("project-switcher-dropdown", "options"),
        Output("project-switcher-dropdown", "value"),
        Output("home-view", "children"),
        Output("nav-tabs-container", "style", allow_duplicate=True),
        Output("sidebar-settings-btn", "disabled"),
        Output("view-selector", "options"),
        Output("settings-view", "children"),
        Output("scenario-css-container", "children", allow_duplicate=True),
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
        """Handle project loading and switching."""
        global _current_project_path

        trigger_id = ctx.triggered_id if ctx.triggered_id else None
        path_to_load = None

        if trigger_id in ("load-project-btn", "project-path-input") and path_input:
            path_to_load = path_input
        elif trigger_id == "project-switcher-dropdown" and dropdown_value:
            # Don't reload if already on this project
            if dropdown_value == current_path:
                raise PreventUpdate
            path_to_load = dropdown_value

        if not path_to_load:
            raise PreventUpdate

        success, message = load_project(path_to_load)
        if not success:
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
                no_update,
                no_update,
                no_update,
            )

        # Build successful load response
        data_handler = _get_current_data_handler()
        color_manager = _get_current_color_manager()

        if not data_handler or not color_manager:
            return (
                no_update,
                html.Span("Failed to initialize project", className="text-danger"),
                no_update,
                no_update,
                no_update,
                no_update,
                no_update,
                no_update,
                no_update,
                no_update,
                no_update,
                no_update,
            )

        project_name = data_handler.project.config.project_id
        new_scenarios = data_handler.scenarios
        new_years = data_handler.years
        loaded_path: str = _current_project_path or ""

        # Add to dropdown if not there
        existing_paths = {opt.get("value") for opt in current_options}
        if loaded_path not in existing_paths:
            new_options: list[dict[str, str]] = [
                {"label": project_name, "value": loaded_path},
                *current_options,
            ]
        else:
            new_options = current_options

        # Create layouts for the loaded project
        new_home_layout = create_home_layout(new_scenarios, new_years, color_manager)

        nav_options = [
            {"label": "Home", "value": "compare"},
            *[{"label": s, "value": s} for s in new_scenarios],
        ]

        # Create settings layout
        try:
            user_palettes_paths = list_user_palettes()
            user_palettes = [p.stem for p in user_palettes_paths]
        except Exception as e:
            logger.warning(f"Could not list user palettes: {e}")
            user_palettes = []

        settings_layout = create_settings_layout(
            project_palette_name=project_name,
            user_palettes=user_palettes,
            current_palette_type="project",
            current_palette_name=None,
            color_manager=color_manager,
        )

        scenario_css = _generate_scenario_css_script(color_manager)

        return (
            loaded_path,
            html.Span(message, className="text-success"),
            project_name,
            loaded_path,
            new_options,
            loaded_path,
            new_home_layout,
            {"display": "block"},
            False,
            nav_options,
            settings_layout,
            scenario_css,
        )


# ============================================================================
# No-project mode
# ============================================================================


def create_app_no_project(
    user_palette: ColorPalette | None = None,
) -> Dash:
    """Create the Dash application without a project loaded.

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

    # Note: We don't create a color manager here - it will be created when a project loads

    # Get recent projects for the dropdown
    available_projects = _get_recent_project_options()
    dropdown_options = []
    for p in available_projects:
        project_id = p.get("project_id", "")
        if project_id:
            dropdown_options.append(
                {"label": p.get("name", project_id), "value": p.get("path", "")}
            )

    # Create layout using shared components
    sidebar = _create_sidebar(
        current_project_name="No project loaded",
        current_project_path="",
        dropdown_options=dropdown_options,
        dropdown_value=None,
        dropdown_placeholder="Select a recent project...",
        settings_disabled=True,
        dropdown_clearable=True,
    )

    welcome_message = _create_welcome_message()

    app.layout = html.Div(
        [
            *_create_state_stores(
                current_project_path="",
                current_palette_type="default",
                current_palette_name=None,
            ),
            _create_scenario_css_container(None),
            sidebar,
            html.Div(
                [
                    _create_header(),
                    _create_nav_tabs([], hidden=True),
                    html.Div(
                        [
                            html.Div(id="home-view", hidden=False, children=[welcome_message]),
                            html.Div(id="scenario-view", hidden=True, children=[]),
                            html.Div(id="settings-view", hidden=True, children=[]),
                        ],
                        id="main-content-container",
                    ),
                ],
                id="page-content",
                className="page-content dark-theme",
                style=CONTENT_STYLE_SIDEBAR_CLOSED,
            ),
        ],
        className="dark-theme",
    )

    # Register callbacks - same as create_app but with empty initial data
    _register_common_callbacks()
    _register_project_callbacks()

    register_home_callbacks(
        _get_current_data_handler,
        _get_current_plotter,
        [],  # Initial empty scenarios - populated when project loads
        literal_to_list(Sectors),
        [],  # Initial empty years - populated when project loads
        _get_current_color_manager,
    )

    register_scenario_callbacks(_get_current_data_handler, _get_current_plotter)

    register_settings_callbacks(
        _get_current_data_handler,
        _get_current_color_manager,
        _on_palette_change,
    )

    return app
