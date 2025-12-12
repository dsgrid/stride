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

    # The ColorPalette stores colors in a flat dict (palette.palette)
    # We need to organize them by inferring groups based on common patterns
    # For now, we'll just display all colors in one group since we don't have
    # group metadata in the ColorPalette class itself

    # Get all colors from the palette
    all_colors = palette.to_dict()

    # Try to categorize by common naming patterns
    scenario_colors = {}
    sector_colors = {}
    end_use_colors = {}

    # Common sector names
    sector_keywords = ["residential", "commercial", "industrial", "transport"]
    # Common end use names
    end_use_keywords = ["heating", "cooling", "lighting", "water", "appliance", "ventilation"]

    for label, color in all_colors.items():
        label_lower = label.lower()
        # Convert color to RGBA format for display
        display_color = color_manager.get_color(label)

        # Categorize based on keywords
        if any(keyword in label_lower for keyword in sector_keywords):
            sector_colors[label] = display_color
        elif any(keyword in label_lower for keyword in end_use_keywords):
            end_use_colors[label] = display_color
        else:
            # Default to scenarios for anything else
            scenario_colors[label] = display_color

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
                                                    html.Div(
                                                        [
                                                            dbc.Button(
                                                                "Apply Palette",
                                                                id="apply-palette-btn",
                                                                color="primary",
                                                                className="mt-3",
                                                            ),
                                                            dbc.Spinner(
                                                                html.Div(
                                                                    id="apply-palette-status"
                                                                ),
                                                                size="sm",
                                                                spinner_style={
                                                                    "marginLeft": "10px"
                                                                },
                                                            ),
                                                        ],
                                                        className="d-flex align-items-center",
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
                                                    # Sectors
                                                    html.Div(
                                                        [
                                                            html.H6(
                                                                "Sectors",
                                                                className="mb-2 text-muted",
                                                            ),
                                                            html.Div(
                                                                [
                                                                    _create_color_item(
                                                                        label, color, temp_edits
                                                                    )
                                                                    for label, color in sector_colors.items()
                                                                ],
                                                                className="d-flex flex-wrap gap-2 mb-3",
                                                            ),
                                                        ]
                                                    )
                                                    if sector_colors
                                                    else None,
                                                    # End Uses
                                                    html.Div(
                                                        [
                                                            html.H6(
                                                                "End Uses",
                                                                className="mb-2 text-muted",
                                                            ),
                                                            html.Div(
                                                                [
                                                                    _create_color_item(
                                                                        label, color, temp_edits
                                                                    )
                                                                    for label, color in end_use_colors.items()
                                                                ],
                                                                className="d-flex flex-wrap gap-2",
                                                            ),
                                                        ]
                                                    )
                                                    if end_use_colors
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
                                                        type="color",
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
                    # Hidden store for selected color label
                    dcc.Store(id="selected-color-label", data=None),
                    # Hidden store for tracking color edits (triggers refresh)
                    dcc.Store(id="color-edits-counter", data=0),
                    # Save Options Section
                    dbc.Row(
                        [
                            dbc.Col(
                                [
                                    html.H4("Save Options", className="mb-3"),
                                    dbc.Card(
                                        [
                                            dbc.CardBody(
                                                [
                                                    html.P(
                                                        "Save the current color scheme to:",
                                                        className="mb-3",
                                                    ),
                                                    dbc.ButtonGroup(
                                                        [
                                                            dbc.Button(
                                                                "Save to Project",
                                                                id="save-to-project-btn",
                                                                color="success",
                                                                outline=True,
                                                            ),
                                                            dbc.Button(
                                                                "Save to User Palette",
                                                                id="save-to-user-btn",
                                                                color="success",
                                                                outline=True,
                                                            ),
                                                        ],
                                                        className="mb-3",
                                                    ),
                                                    html.Div(id="save-palette-status"),
                                                    # User palette name input (hidden by default)
                                                    html.Div(
                                                        [
                                                            html.Label(
                                                                "User Palette Name:",
                                                                className="form-label",
                                                            ),
                                                            dbc.Input(
                                                                id="save-user-palette-name",
                                                                type="text",
                                                                placeholder="Enter palette name...",
                                                            ),
                                                        ],
                                                        id="save-user-palette-name-container",
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
                        ]
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

    # Get all colors from the palette
    all_colors = palette.to_dict()

    # Try to categorize by common naming patterns
    scenario_colors = {}
    sector_colors = {}
    end_use_colors = {}

    # Common sector names
    sector_keywords = ["residential", "commercial", "industrial", "transport"]
    # Common end use names
    end_use_keywords = ["heating", "cooling", "lighting", "water", "appliance", "ventilation"]

    for label, color in all_colors.items():
        label_lower = label.lower()
        # Convert color to RGBA format for display
        display_color = color_manager.get_color(label)

        # Categorize based on keywords
        if any(keyword in label_lower for keyword in sector_keywords):
            sector_colors[label] = display_color
        elif any(keyword in label_lower for keyword in end_use_keywords):
            end_use_colors[label] = display_color
        else:
            # Default to scenarios for anything else
            scenario_colors[label] = display_color

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

    # Sectors
    if sector_colors:
        content.append(
            html.Div(
                [
                    html.H6(
                        "Sectors",
                        className="mb-2 text-muted",
                    ),
                    html.Div(
                        [
                            _create_color_item(label, color, temp_edits)
                            for label, color in sector_colors.items()
                        ],
                        className="d-flex flex-wrap gap-2 mb-3",
                    ),
                ]
            )
        )

    # End Uses
    if end_use_colors:
        content.append(
            html.Div(
                [
                    html.H6(
                        "End Uses",
                        className="mb-2 text-muted",
                    ),
                    html.Div(
                        [
                            _create_color_item(label, color, temp_edits)
                            for label, color in end_use_colors.items()
                        ],
                        className="d-flex flex-wrap gap-2",
                    ),
                ]
            )
        )

    return content
