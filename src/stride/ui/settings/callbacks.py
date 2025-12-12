"""Settings page callbacks for STRIDE dashboard."""

import re
from typing import Any

from dash import ALL, Input, Output, State, callback, ctx, html, no_update
from dash.exceptions import PreventUpdate
from loguru import logger

from stride.ui.palette import ColorPalette
from stride.ui.settings.layout import (
    clear_temp_color_edits,
    create_color_preview_content,
    get_temp_color_edits,
    set_temp_color_edit,
)
from stride.ui.tui import load_user_palette, save_user_palette


def register_settings_callbacks(  # type: ignore[no-untyped-def]  # noqa: C901
    get_data_handler_func,
    get_color_manager_func,
    on_palette_change_func,
) -> None:
    """
    Register callbacks for the settings page.

    Parameters
    ----------
    get_data_handler_func : callable
        Function to get the current data handler instance
    get_color_manager_func : callable
        Function to get the current color manager instance
    on_palette_change_func : callable
        Function to call when palette changes (to refresh the app)
    """

    @callback(
        Output("color-edits-counter", "data"),
        Input("color-picker-apply-btn", "n_clicks"),
        State("color-edits-counter", "data"),
        prevent_initial_call=True,
    )
    def increment_color_edits_counter(
        apply_clicks: int | None,
        current_counter: int,
    ) -> int:
        """Increment counter when a color is applied to trigger UI refresh."""
        if not apply_clicks:
            raise PreventUpdate
        return current_counter + 1

    @callback(
        Output("color-picker-modal", "is_open"),
        Output("selected-color-label", "data"),
        Output("color-picker-modal-title", "children"),
        Output("color-picker-input", "value"),
        Output("color-picker-hex-input", "value"),
        Output("color-edits-counter", "data", allow_duplicate=True),
        Input({"type": "color-item", "index": ALL}, "n_clicks"),
        Input("color-picker-cancel-btn", "n_clicks"),
        Input("color-picker-apply-btn", "n_clicks"),
        State("color-picker-modal", "is_open"),
        State("selected-color-label", "data"),
        State("color-picker-input", "value"),
        State("color-edits-counter", "data"),
        prevent_initial_call=True,
    )
    def toggle_color_picker_modal(  # noqa: C901
        color_clicks: list[int],
        cancel_clicks: int | None,
        apply_clicks: int | None,
        is_open: bool,
        current_label: str | None,
        picked_color: str | None,
        color_counter: int,
    ) -> tuple[bool, str | None, str, str, str, int]:
        """Open/close color picker modal and handle color selection."""
        if not ctx.triggered:
            raise PreventUpdate

        triggered_id = ctx.triggered_id

        # Close modal on cancel
        if triggered_id == "color-picker-cancel-btn":
            return False, None, "", "#000000", "#000000", no_update  # type: ignore[return-value]

        # Close modal and apply color on apply button
        if triggered_id == "color-picker-apply-btn":
            if current_label and picked_color:
                # Store the color change temporarily
                set_temp_color_edit(current_label, picked_color)
                logger.info(f"Temporarily updated color for '{current_label}' to {picked_color}")
                # Increment counter to trigger refresh (will be handled by separate callback)
            return False, None, "", "#000000", "#000000", no_update  # type: ignore[return-value]

        # Open modal when a color item is clicked
        if isinstance(triggered_id, dict) and triggered_id.get("type") == "color-item":
            # Get the index of the clicked item
            index = triggered_id.get("index")
            if index is None:
                raise PreventUpdate

            # If modal is already open, don't reopen it
            # This prevents the modal from jumping between colors
            if is_open:
                raise PreventUpdate

            # Check if this was a real click by examining the triggered property
            # When the refresh happens, n_clicks goes to 0, which shouldn't trigger
            triggered_value = ctx.triggered[0]["value"]

            # Only open if the click count is positive (real click, not a reset to 0)
            if not triggered_value or triggered_value == 0:
                raise PreventUpdate

            # Get the color manager to find the current color
            color_manager = get_color_manager_func()
            if color_manager is None:
                raise PreventUpdate

            # Get current color (check temp edits first)
            temp_edits = get_temp_color_edits()
            if index in temp_edits:
                current_color = temp_edits[index]
            else:
                current_color = color_manager.get_color(index)

            # Convert color to hex format for the color input
            hex_color = _convert_to_hex(current_color)

            return (
                True,
                index,
                f"Edit Color: {index}",
                hex_color,
                hex_color,
                no_update,  # type: ignore[return-value]
            )

        raise PreventUpdate

    @callback(
        Output("color-preview-container", "children"),
        Input("color-edits-counter", "data"),
        Input("settings-palette-applied", "data"),
        prevent_initial_call=True,
    )
    def refresh_color_preview(counter: int, palette_data: dict[str, Any]) -> list[html.Div]:
        """Refresh the color preview when colors are edited or palette is changed."""
        color_manager = get_color_manager_func()
        if color_manager is None:
            raise PreventUpdate

        # Clear temporary edits when palette is switched
        if ctx.triggered_id == "settings-palette-applied":
            clear_temp_color_edits()
            logger.info("Cleared temporary color edits due to palette change")

        return create_color_preview_content(color_manager)

    @callback(
        Output("color-picker-input", "value", allow_duplicate=True),
        Output("color-picker-hex-input", "value", allow_duplicate=True),
        Input("color-picker-input", "value"),
        Input("color-picker-hex-input", "value"),
        prevent_initial_call=True,
    )
    def sync_color_inputs(color_value: str, hex_value: str) -> tuple[str, str]:
        """Sync color picker and hex input."""
        if not ctx.triggered:
            raise PreventUpdate

        triggered_id = ctx.triggered_id

        # Validate and sync
        if triggered_id == "color-picker-input":
            # Color input changed
            hex_color = color_value
            if _is_valid_hex(hex_color):
                return hex_color, hex_color
            return no_update, no_update  # type: ignore[return-value]

        elif triggered_id == "color-picker-hex-input":
            # Hex input changed
            hex_color = hex_value.strip()
            if not hex_color.startswith("#"):
                hex_color = "#" + hex_color

            if _is_valid_hex(hex_color):
                return hex_color, hex_color
            return no_update, no_update  # type: ignore[return-value]

        raise PreventUpdate

    @callback(
        Output("user-palette-selector-container", "style"),
        Output("user-palette-selector", "disabled"),
        Input("palette-type-selector", "value"),
    )
    def toggle_user_palette_selector(palette_type: str) -> tuple[dict[str, str], bool]:
        """Show/hide user palette selector based on palette type selection."""
        if palette_type == "user":
            return {"display": "block"}, False
        else:
            return {"display": "none"}, True

    @callback(
        Output("apply-palette-status", "children"),
        Output("settings-palette-applied", "data", allow_duplicate=True),
        Input("apply-palette-btn", "n_clicks"),
        State("palette-type-selector", "value"),
        State("user-palette-selector", "value"),
        prevent_initial_call=True,
    )
    def apply_palette(
        n_clicks: int | None,
        palette_type: str,
        user_palette_name: str | None,
    ) -> tuple[html.Div, dict[str, Any]]:
        """Apply the selected palette."""
        if not n_clicks:
            raise PreventUpdate

        try:
            data_handler = get_data_handler_func()
            if data_handler is None:
                return (
                    html.Div(
                        "✗ Error: No project loaded",
                        className="text-danger mt-2",
                    ),
                    no_update,  # type: ignore[return-value]
                )

            if palette_type == "project":
                # Use project palette
                palette = data_handler.project.palette
                on_palette_change_func(palette, "project", None)
                logger.info("Applied project palette")
                return (
                    html.Div(
                        "✓ Project palette applied",
                        className="text-success mt-2",
                    ),
                    {"type": "project", "name": None},
                )
            elif palette_type == "user":
                if not user_palette_name:
                    return (
                        html.Div(
                            "⚠ Please select a user palette",
                            className="text-warning mt-2",
                        ),
                        no_update,  # type: ignore[return-value]
                    )
                # Load and apply user palette
                try:
                    logger.info(f"Attempting to load user palette: {user_palette_name}")
                    palette = load_user_palette(user_palette_name)
                    logger.info("Palette loaded successfully, applying changes")
                    on_palette_change_func(palette, "user", user_palette_name)
                    logger.info(f"Applied user palette: {user_palette_name}")
                    return (
                        html.Div(
                            f"✓ User palette '{user_palette_name}' applied",
                            className="text-success mt-2",
                        ),
                        {"type": "user", "name": user_palette_name},
                    )
                except FileNotFoundError as e:
                    logger.error(
                        f"FileNotFoundError - User palette not found: {user_palette_name}"
                    )
                    logger.error(f"Exception message: {str(e)}")
                    # Show only the palette name, not the full path
                    return (
                        html.Div(
                            f"✗ Palette '{user_palette_name}' not found",
                            className="text-danger mt-2",
                        ),
                        no_update,  # type: ignore[return-value]
                    )
                except Exception as e:
                    logger.error(f"Error loading user palette '{user_palette_name}': {e}")
                    logger.error(f"Exception type: {type(e).__name__}")
                    import traceback

                    logger.error(f"Traceback: {traceback.format_exc()}")
                    # Extract just the error message without the path if present
                    error_msg = str(e)
                    if user_palette_name in error_msg:
                        # Show a clean error message
                        error_msg = f"Error loading palette '{user_palette_name}'"
                    return (
                        html.Div(
                            f"✗ {error_msg}",
                            className="text-danger mt-2",
                        ),
                        no_update,  # type: ignore[return-value]
                    )
            else:
                # Unknown palette type
                return (
                    html.Div(
                        "✗ Invalid palette type",
                        className="text-danger mt-2",
                    ),
                    no_update,  # type: ignore[return-value]
                )
        except Exception as e:
            logger.error(f"Error applying palette: {e}")
            return (
                html.Div(
                    f"✗ Error: {str(e)}",
                    className="text-danger mt-2",
                ),
                no_update,  # type: ignore[return-value]
            )

    @callback(
        Output("save-user-palette-name-container", "style"),
        Input("save-to-user-btn", "n_clicks"),
        prevent_initial_call=True,
    )
    def show_user_palette_name_input(n_clicks: int | None) -> dict[str, str]:
        """Show the user palette name input when save to user button is clicked."""
        if not n_clicks:
            raise PreventUpdate
        return {"display": "block"}

    @callback(
        Output("save-palette-status", "children"),
        Input("save-to-project-btn", "n_clicks"),
        State("settings-palette-applied", "data"),
        prevent_initial_call=True,
    )
    def save_to_project(
        n_clicks: int | None,
        current_palette_data: dict[str, Any],
    ) -> html.Div:
        """Save current palette to project.json."""
        if not n_clicks:
            raise PreventUpdate

        try:
            data_handler = get_data_handler_func()
            color_manager = get_color_manager_func()

            if data_handler is None or color_manager is None:
                return html.Div(
                    "✗ Error: No project loaded",
                    className="text-danger mt-2",
                )

            # Apply temporary edits to palette
            temp_edits = get_temp_color_edits()
            palette = color_manager.get_palette()
            for label, color in temp_edits.items():
                palette.update(label, color)

            # Extract colors from color manager's palette
            current_palette = color_manager.get_palette()

            # Get all colors as a flat dict - ColorPalette stores colors this way
            palette_data = current_palette.to_dict()

            # Create ColorPalette and save to project
            palette = ColorPalette(palette_data)
            data_handler.project.save_palette()

            # Clear temporary edits after saving
            clear_temp_color_edits()

            logger.info("Saved palette to project")
            return html.Div(
                "✓ Palette saved to project.json",
                className="text-success mt-2",
            )
        except Exception as e:
            logger.error(f"Error saving palette to project: {e}")
            return html.Div(
                f"✗ Error: {str(e)}",
                className="text-danger mt-2",
            )

    @callback(
        Output("save-palette-status", "children", allow_duplicate=True),
        Output("save-user-palette-name-container", "style", allow_duplicate=True),
        Output("save-user-palette-name", "value"),
        Input("save-to-user-btn", "n_clicks"),
        State("save-user-palette-name", "value"),
        prevent_initial_call=True,
    )
    def save_to_user(
        n_clicks: int | None,
        palette_name: str | None,
    ) -> tuple[html.Div, dict[str, str], str]:
        """Save current palette to user palette."""
        if not n_clicks:
            raise PreventUpdate

        # First click shows input, second click saves
        if not palette_name or palette_name.strip() == "":
            return (
                html.Div(
                    "⚠ Enter a name for the user palette above",
                    className="text-warning mt-2",
                ),
                {"display": "block"},
                "",
            )

        try:
            color_manager = get_color_manager_func()

            # Apply temporary edits to palette
            temp_edits = get_temp_color_edits()
            palette = color_manager.get_palette()
            for label, color in temp_edits.items():
                palette.update(label, color)

            # Extract colors from color manager's palette
            current_palette = color_manager.get_palette()

            # Get all colors as a flat dict - ColorPalette stores colors this way
            palette_data = current_palette.to_dict()

            # Save palette data directly (save_user_palette expects name first, then dict)
            save_user_palette(palette_name.strip(), palette_data)

            # Clear temporary edits after saving
            clear_temp_color_edits()

            logger.info(f"Saved palette to user palettes: {palette_name}")
            return (
                html.Div(
                    f"✓ Palette saved as '{palette_name.strip()}'",
                    className="text-success mt-2",
                ),
                {"display": "none"},
                "",
            )
        except Exception as e:
            logger.error(f"Error saving palette to user: {e}")
            return (
                html.Div(
                    f"✗ Error: {str(e)}",
                    className="text-danger mt-2",
                ),
                {"display": "block"},
                palette_name,
            )


def _convert_to_hex(color: str) -> str:
    """
    Convert a color string to hex format.

    Parameters
    ----------
    color : str
        Color in any format (hex, rgb, rgba, named)

    Returns
    -------
    str
        Color in hex format (#RRGGBB)
    """
    # If already hex, return it
    if color.startswith("#"):
        # Ensure it's 6 digits (not 3)
        if len(color) == 4:  # #RGB
            return f"#{color[1]}{color[1]}{color[2]}{color[2]}{color[3]}{color[3]}"
        return color[:7]  # Return first 7 chars to ignore alpha

    # Parse rgb/rgba format
    rgb_match = re.match(r"rgba?\((\d+),\s*(\d+),\s*(\d+)", color)
    if rgb_match:
        r, g, b = map(int, rgb_match.groups())
        return f"#{r:02x}{g:02x}{b:02x}"

    # Default to black if can't parse
    return "#000000"


def _is_valid_hex(color: str) -> bool:
    """
    Check if a color string is a valid hex color.

    Parameters
    ----------
    color : str
        Color string to validate

    Returns
    -------
    bool
        True if valid hex color
    """
    if not color.startswith("#"):
        return False
    hex_part = color[1:]
    return len(hex_part) in (3, 6) and all(c in "0123456789ABCDEFabcdef" for c in hex_part)
