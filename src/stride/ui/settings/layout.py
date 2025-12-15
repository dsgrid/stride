"""Settings page layout for STRIDE dashboard."""

import dash_bootstrap_components as dbc
from dash import dcc, html

from stride.ui.color_manager import ColorManager

# Store for temporarily edited colors before saving
_temp_color_edits: dict[str, str] = {}


def create_settings_layout(
    project_palette_name: str,
    user_palettes: list[str],
    current_palette_type: str,
    current_palette_name: str | None,
    color_manager: ColorManager,
) -> html.Div:
    """
    Create the settings page layout.

    Parameters
    ----------
    project_palette_name : str
        Name of the project's palette
    user_palettes : list[str]
        List of available user palette names
    current_palette_type : str
        Currently active palette type ('project' or 'user')
    current_palette_name : str | None
        Name of currently active user palette (if type is 'user')
    color_manager : ColorManager
        Color manager instance for displaying current colors

    Returns
    -------
    html.Div
        Settings page layout
    """
    # Get current palette data from color manager's palette
    palette = color_manager.get_palette()

    # Get structured palette with categories
    structured_palette = palette.to_dict()

    # Extract colors for each category and convert to RGBA for display
    scenario_colors = {}
    for label in structured_palette.get("scenarios", {}):
        scenario_colors[label] = color_manager.get_color(label)

    model_year_colors = {}
    for label in structured_palette.get("model_years", {}):
        model_year_colors[label] = color_manager.get_color(label)

    metric_colors = {}
    for label in structured_palette.get("metrics", {}):
        metric_colors[label] = color_manager.get_color(label)

    # Get temporary color edits
    temp_edits = get_temp_color_edits()

    return html.Div(
        [
            dbc.Container(
                [
                    # Header
                    dbc.Row(
                        [
                            dbc.Col(
                                [
                                    html.H2("Settings", className="mb-4"),
                                    html.Hr(),
                                ]
                            )
                        ]
                    ),
                    # Palette Selection Section
                    dbc.Row(
                        [
                            dbc.Col(
                                [
                                    html.H4("Color Palette", className="mb-3"),
                                    dbc.Card(
                                        [
                                            dbc.CardBody(
                                                [
                                                    html.Label(
                                                        "Select Palette Source:",
                                                        className="form-label fw-bold",
                                                    ),
                                                    dbc.RadioItems(
                                                        id="palette-type-selector",
                                                        options=[
                                                            {
                                                                "label": f"Project Palette ({project_palette_name})",
                                                                "value": "project",
                                                            },
                                                            {
                                                                "label": "User Palette",
                                                                "value": "user",
                                                            },
                                                        ],
                                                        value=current_palette_type,
                                                        className="mb-3",
                                                    ),
                                                    html.Div(
                                                        [
                                                            html.Label(
                                                                "Select User Palette:",
                                                                className="form-label",
                                                            ),
                                                            dcc.Dropdown(
                                                                id="user-palette-selector",
                                                                options=[
                                                                    {"label": p, "value": p}
                                                                    for p in user_palettes
                                                                ],
                                                                value=current_palette_name,
                                                                placeholder="Select a user palette...",
                                                                disabled=(
                                                                    current_palette_type
                                                                    == "project"
                                                                ),
                                                            ),
                                                        ],
                                                        id="user-palette-selector-container",
                                                        style={
                                                            "display": (
                                                                "block"
                                                                if current_palette_type == "user"
                                                                else "none"
                                                            )
                                                        },
                                                    ),
                                                ]
                                            )
                                        ],
                                        className="mb-4",
                                    ),
                                ]
                            )
                        ]
                    ),
                    # Current Colors Preview Section
                    dbc.Row(
                        [
                            dbc.Col(
                                [
                                    html.H4("Current Color Scheme", className="mb-3"),
                                    html.P(
                                        "Click any color to edit it with the color picker.",
                                        className="text-muted small mb-3",
                                    ),
                                    dbc.Card(
                                        [
                                            dbc.CardBody(
                                                id="color-preview-container",
                                                children=[
                                                    # Scenarios
                                                    html.Div(
                                                        [
                                                            html.H6(
                                                                "Scenarios",
                                                                className="mb-2 text-muted",
                                                            ),
                                                            html.Div(
                                                                [
                                                                    _create_color_item(
                                                                        label, color, temp_edits
                                                                    )
                                                                    for label, color in scenario_colors.items()
                                                                ],
                                                                className="d-flex flex-wrap gap-2 mb-3",
                                                            ),
                                                        ]
                                                    )
                                                    if scenario_colors
                                                    else None,
                                                    # Model Years
                                                    html.Div(
                                                        [
                                                            html.H6(
                                                                "Model Years",
                                                                className="mb-2 text-muted",
                                                            ),
                                                            html.Div(
                                                                [
                                                                    _create_color_item(
                                                                        label, color, temp_edits
                                                                    )
                                                                    for label, color in model_year_colors.items()
                                                                ],
                                                                className="d-flex flex-wrap gap-2 mb-3",
                                                            ),
                                                        ]
                                                    )
                                                    if model_year_colors
                                                    else None,
                                                    # Metrics
                                                    html.Div(
                                                        [
                                                            html.H6(
                                                                "Metrics",
                                                                className="mb-2 text-muted",
                                                            ),
                                                            html.Div(
                                                                [
                                                                    _create_color_item(
                                                                        label, color, temp_edits
                                                                    )
                                                                    for label, color in metric_colors.items()
                                                                ],
                                                                className="d-flex flex-wrap gap-2",
                                                            ),
                                                        ]
                                                    )
                                                    if metric_colors
                                                    else None,
                                                ],
                                            )
                                        ],
                                        className="mb-4",
                                    ),
                                ]
                            )
                        ]
                    ),
                    # JSON Editor Section
                    dbc.Row(
                        [
                            dbc.Col(
                                [
                                    html.Div(
                                        [
                                            html.H4("Advanced: JSON Editor", className="mb-2"),
                                            dbc.Button(
                                                [
                                                    html.I(className="bi bi-chevron-down me-2"),
                                                    "Show JSON Editor",
                                                ],
                                                id="toggle-json-editor-btn",
                                                color="secondary",
                                                outline=True,
                                                size="sm",
                                                className="mb-3",
                                            ),
                                        ]
                                    ),
                                    dbc.Collapse(
                                        dbc.Card(
                                            [
                                                dbc.CardBody(
                                                    [
                                                        html.P(
                                                            "Edit the palette as JSON. Paste a new palette and click 'Apply JSON' to update the preview. Changes are not saved until you use one of the save buttons below.",
                                                            className="text-muted small mb-3",
                                                        ),
                                                        dbc.Textarea(
                                                            id="palette-json-editor",
                                                            style={
                                                                "fontFamily": "monospace",
                                                                "fontSize": "0.85rem",
                                                                "minHeight": "300px",
                                                            },
                                                            className="mb-3",
                                                        ),
                                                        html.Div(
                                                            [
                                                                dbc.Button(
                                                                    "Apply JSON",
                                                                    id="apply-json-btn",
                                                                    color="primary",
                                                                    size="sm",
                                                                    className="me-2",
                                                                ),
                                                                dbc.Button(
                                                                    "Reset to Current",
                                                                    id="reset-json-btn",
                                                                    color="secondary",
                                                                    size="sm",
                                                                ),
                                                            ],
                                                            className="mb-2",
                                                        ),
                                                        html.Div(id="json-editor-status"),
                                                    ]
                                                )
                                            ],
                                            className="mb-4",
                                        ),
                                        id="json-editor-collapse",
                                        is_open=False,
                                    ),
                                ]
                            )
                        ]
                    ),
                    # Color Picker Modal
                    dbc.Modal(
                        [
                            dbc.ModalHeader(
                                dbc.ModalTitle(id="color-picker-modal-title"),
                                close_button=True,
                            ),
                            dbc.ModalBody(
                                [
                                    html.Div(
                                        [
                                            html.Label(
                                                "Select Color:",
                                                className="form-label fw-bold mb-2",
                                            ),
                                            html.Div(
                                                [
                                                    dbc.Input(
                                                        id="color-picker-input",
                                                        type="color",  # type: ignore[arg-type]
                                                        style={
                                                            "width": "100%",
                                                            "height": "60px",
                                                            "cursor": "pointer",
                                                        },
                                                    ),
                                                ],
                                                className="mb-3",
                                            ),
                                            html.Div(
                                                [
                                                    html.Label(
                                                        "Or enter hex color:",
                                                        className="form-label mb-2",
                                                    ),
                                                    dbc.Input(
                                                        id="color-picker-hex-input",
                                                        type="text",
                                                        placeholder="#RRGGBB",
                                                        debounce=True,
                                                    ),
                                                ],
                                                className="mb-3",
                                            ),
                                        ]
                                    ),
                                ]
                            ),
                            dbc.ModalFooter(
                                [
                                    dbc.Button(
                                        "Cancel",
                                        id="color-picker-cancel-btn",
                                        color="secondary",
                                        className="me-2",
                                    ),
                                    dbc.Button(
                                        "Apply",
                                        id="color-picker-apply-btn",
                                        color="primary",
                                    ),
                                ]
                            ),
                        ],
                        id="color-picker-modal",
                        is_open=False,
                        size="md",
                        centered=True,
                    ),
                    # Delete Confirmation Modal
                    dbc.Modal(
                        [
                            dbc.ModalHeader(
                                dbc.ModalTitle("Confirm Delete"),
                                close_button=True,
                            ),
                            dbc.ModalBody(
                                [
                                    html.P(
                                        id="delete-confirmation-text",
                                        className="mb-0",
                                    ),
                                ]
                            ),
                            dbc.ModalFooter(
                                [
                                    dbc.Button(
                                        "Cancel",
                                        id="delete-cancel-btn",
                                        color="secondary",
                                        className="me-2",
                                    ),
                                    dbc.Button(
                                        "Delete",
                                        id="delete-confirm-btn",
                                        color="danger",
                                    ),
                                ]
                            ),
                        ],
                        id="delete-confirmation-modal",
                        is_open=False,
                        size="md",
                        centered=True,
                    ),
                    # Hidden store for selected color label
                    dcc.Store(id="selected-color-label", data=None),
                    # Hidden store for tracking color edits (triggers refresh)
                    dcc.Store(id="color-edits-counter", data=0),
                    # Save Options Section
                    dbc.Row(
                        html.Div(
                            [
                                dbc.Col(
                                    [
                                        html.H4("Save Options", className="mb-3"),
                                        dbc.Card(
                                            [
                                                dbc.CardBody(
                                                    [
                                                        html.P(
                                                            "Save the current color scheme:",
                                                            className="mb-3",
                                                        ),
                                                        html.Div(
                                                            [
                                                                dbc.Button(
                                                                    "Save Current Palette",
                                                                    id="save-current-palette-btn",
                                                                    color="primary",
                                                                    outline=True,
                                                                    className="m-1 theme-text",
                                                                ),
                                                                dbc.Button(
                                                                    "Save to Project",
                                                                    id="save-to-project-btn",
                                                                    color="success",
                                                                    outline=True,
                                                                    className="m-1 theme-text",
                                                                ),
                                                                dbc.Button(
                                                                    "Save to New Palette",
                                                                    id="save-to-new-palette-btn",
                                                                    color="info",
                                                                    outline=True,
                                                                    className="m-1 theme-text",
                                                                ),
                                                                dbc.Button(
                                                                    "Revert Changes",
                                                                    id="revert-changes-btn",
                                                                    color="warning",
                                                                    outline=True,
                                                                    className="m-1 theme-text",
                                                                ),
                                                                dbc.Button(
                                                                    "Delete Selected User Palette",
                                                                    id="delete-user-palette-btn",
                                                                    color="danger",
                                                                    outline=True,
                                                                    className="m-1 theme-text",
                                                                    disabled=(
                                                                        current_palette_type
                                                                        == "project"
                                                                        or not current_palette_name
                                                                    ),
                                                                ),
                                                            ],
                                                            className="d-flex flex-wrap mb-3",
                                                        ),
                                                        html.Div(id="revert-changes-status"),
                                                        html.Div(id="delete-palette-status"),
                                                        html.Div(id="save-palette-status"),
                                                        # New palette name input (hidden by default)
                                                        html.Div(
                                                            [
                                                                html.Label(
                                                                    "New Palette Name:",
                                                                    className="form-label",
                                                                ),
                                                                dbc.Input(
                                                                    id="save-new-palette-name",
                                                                    type="text",
                                                                    placeholder="Enter new palette name...",
                                                                ),
                                                            ],
                                                            id="save-new-palette-name-container",
                                                            style={"display": "none"},
                                                            className="mt-3",
                                                        ),
                                                    ]
                                                )
                                            ],
                                            className="mb-4",
                                        ),
                                    ]
                                )
                            ],
                        )
                    ),
                    # Back button
                    dbc.Row(
                        [
                            dbc.Col(
                                [
                                    dbc.Button(
                                        "← Back to Dashboard",
                                        id="back-to-dashboard-btn",
                                        color="secondary",
                                        className="mb-4",
                                    )
                                ]
                            )
                        ]
                    ),
                ],
                fluid=True,
                className="mt-4",
            )
        ]
    )


def _create_color_item(label: str, color: str, temp_edits: dict[str, str]) -> html.Div:
    """
    Create a color preview item with label.

    Parameters
    ----------
    label : str
        Label name
    color : str
        Color value (hex, rgb, or rgba)
    temp_edits : dict[str, str]
        Dictionary of temporary color edits

    Returns
    -------
    html.Div
        Color preview component
    """
    # Check if there's a temporary edit for this color
    display_color = temp_edits.get(label, color)

    return html.Div(
        [
            html.Button(
                [
                    html.Div(
                        style={
                            "width": "30px",
                            "height": "30px",
                            "backgroundColor": display_color,
                            "border": "1px solid #ddd",
                            "borderRadius": "4px",
                            "display": "inline-block",
                            "verticalAlign": "middle",
                        }
                    ),
                    html.Span(
                        label,
                        style={
                            "marginLeft": "8px",
                            "verticalAlign": "middle",
                            "fontSize": "0.9rem",
                        },
                    ),
                ],
                id={"type": "color-item", "index": label},
                n_clicks=0,
                style={
                    "display": "inline-flex",
                    "alignItems": "center",
                    "padding": "6px 12px",
                    "backgroundColor": "#f8f9fa",
                    "borderRadius": "4px",
                    "border": "1px solid #dee2e6",
                    "cursor": "pointer",
                    "transition": "all 0.2s",
                },
                className="color-item-button",
            ),
        ],
        **{"data-color-label": label},  # type: ignore[arg-type]
    )


def get_temp_color_edits() -> dict[str, str]:
    """Get the temporary color edits dictionary."""
    return _temp_color_edits


def clear_temp_color_edits() -> None:
    """Clear all temporary color edits."""
    _temp_color_edits.clear()


def set_temp_color_edit(label: str, color: str) -> None:
    """Set a temporary color edit."""
    _temp_color_edits[label] = color


def create_color_preview_content(color_manager: ColorManager) -> list[html.Div]:
    """
    Create the color preview content with current colors and temp edits.

    Parameters
    ----------
    color_manager : ColorManager
        Color manager instance for displaying current colors

    Returns
    -------
    list
        List of HTML components for the color preview
    """
    # Get current palette data from color manager's palette
    palette = color_manager.get_palette()

    # Get structured palette with categories
    structured_palette = palette.to_dict()

    # Extract colors for each category and convert to RGBA for display
    scenario_colors = {}
    for label in structured_palette.get("scenarios", {}):
        scenario_colors[label] = color_manager.get_color(label)

    model_year_colors = {}
    for label in structured_palette.get("model_years", {}):
        model_year_colors[label] = color_manager.get_color(label)

    metric_colors = {}
    for label in structured_palette.get("metrics", {}):
        metric_colors[label] = color_manager.get_color(label)

    # Get temporary color edits
    temp_edits = get_temp_color_edits()

    # Build the content
    content = []

    # Scenarios
    if scenario_colors:
        content.append(
            html.Div(
                [
                    html.H6(
                        "Scenarios",
                        className="mb-2 text-muted",
                    ),
                    html.Div(
                        [
                            _create_color_item(label, color, temp_edits)
                            for label, color in scenario_colors.items()
                        ],
                        className="d-flex flex-wrap gap-2 mb-3",
                    ),
                ]
            )
        )

    # Model Years
    if model_year_colors:
        content.append(
            html.Div(
                [
                    html.H6(
                        "Model Years",
                        className="mb-2 text-muted",
                    ),
                    html.Div(
                        [
                            _create_color_item(label, color, temp_edits)
                            for label, color in model_year_colors.items()
                        ],
                        className="d-flex flex-wrap gap-2 mb-3",
                    ),
                ]
            )
        )

    # Metrics
    if metric_colors:
        content.append(
            html.Div(
                [
                    html.H6(
                        "Metrics",
                        className="mb-2 text-muted",
                    ),
                    html.Div(
                        [
                            _create_color_item(label, color, temp_edits)
                            for label, color in metric_colors.items()
                        ],
                        className="d-flex flex-wrap gap-2",
                    ),
                ]
            )
        )

    return content
