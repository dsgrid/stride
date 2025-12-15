"""Settings page callbacks for STRIDE dashboard."""

import json
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
from stride.ui.tui import (
    delete_user_palette,
    list_user_palettes,
    load_user_palette,
    save_user_palette,
)


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
        Output("delete-user-palette-btn", "disabled"),
        Input("palette-type-selector", "value"),
        State("user-palette-selector", "value"),
    )
    def toggle_user_palette_selector(
        palette_type: str, selected_palette: str | None
    ) -> tuple[dict[str, str], bool, bool]:
        """Enable/disable user palette selector based on palette type."""
        if palette_type == "user":
            return {"display": "block"}, False, not selected_palette
        else:
            return {"display": "none"}, True, True

    @callback(
        Output("delete-user-palette-btn", "disabled", allow_duplicate=True),
        Input("user-palette-selector", "value"),
        State("palette-type-selector", "value"),
        prevent_initial_call=True,
    )
    def update_delete_button(selected_palette: str | None, palette_type: str) -> bool:
        """Enable/disable delete button based on whether a palette is selected."""
        return palette_type == "project" or not selected_palette

    @callback(
        Output("revert-changes-status", "children"),
        Output("color-edits-counter", "data", allow_duplicate=True),
        Output("settings-palette-applied", "data", allow_duplicate=True),
        Input("revert-changes-btn", "n_clicks"),
        State("color-edits-counter", "data"),
        State("settings-palette-applied", "data"),
        prevent_initial_call=True,
    )
    def revert_changes(
        n_clicks: int | None,
        counter: int,
        current_palette_data: dict[str, Any],
    ) -> tuple[html.Div, int, dict[str, Any]]:
        """Revert all unsaved color changes by reloading the palette from disk."""
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
                    counter,
                    current_palette_data,
                )

            # Check if there are any temporary edits
            temp_edits = get_temp_color_edits()
            if not temp_edits:
                return (
                    html.Div(
                        "⚠ No unsaved changes to revert",
                        className="text-warning mt-2",
                    ),
                    counter,
                    current_palette_data,
                )

            # Get the current palette type and name
            palette_type = current_palette_data.get("type", "project")
            palette_name = current_palette_data.get("name")

            # Reload the palette from disk
            if palette_type == "project":
                # Force reload from config by clearing cache and recreating
                data_handler.project._palette = None
                palette = data_handler.project.palette
                logger.info("Reloaded project palette from disk")
            elif palette_type == "user" and palette_name:
                # Reload user palette from file
                palette = load_user_palette(palette_name)
                logger.info(f"Reloaded user palette '{palette_name}' from disk")
            else:
                return (
                    html.Div(
                        "✗ Error: No active palette to revert to",
                        className="text-danger mt-2",
                    ),
                    counter,
                    current_palette_data,
                )

            # Clear temporary edits
            clear_temp_color_edits()

            # Apply the reloaded palette to refresh the UI
            on_palette_change_func(palette, palette_type, palette_name)

            logger.info(f"Reverted {len(temp_edits)} unsaved color changes")

            return (
                html.Div(
                    f"✓ Reverted {len(temp_edits)} unsaved color change(s)",
                    className="text-success mt-2",
                ),
                counter + 1,  # Increment to trigger refresh
                current_palette_data,
            )
        except Exception as e:
            logger.error(f"Error reverting changes: {e}")
            return (
                html.Div(
                    f"✗ Error: {str(e)}",
                    className="text-danger mt-2",
                ),
                counter,
                current_palette_data,
            )

    @callback(
        Output("settings-palette-applied", "data", allow_duplicate=True),
        Output("color-edits-counter", "data", allow_duplicate=True),
        Input("palette-type-selector", "value"),
        Input("user-palette-selector", "value"),
        State("color-edits-counter", "data"),
        prevent_initial_call=True,
    )
    def apply_selected_palette(
        palette_type: str,
        user_palette_name: str | None,
        counter: int,
    ) -> tuple[dict[str, Any], int]:
        """Automatically apply palette when selection changes."""
        try:
            data_handler = get_data_handler_func()
            if data_handler is None:
                raise PreventUpdate

            # Determine which input triggered the callback
            triggered_id = ctx.triggered_id

            if triggered_id == "palette-type-selector" and palette_type == "project":
                # User switched to project palette
                palette = data_handler.project.palette
                on_palette_change_func(palette, "project", None)
                logger.info("Switched to project palette")
                return {"type": "project", "name": None}, counter + 1

            elif (
                triggered_id == "palette-type-selector"
                and palette_type == "user"
                and user_palette_name
            ):
                # User switched back to user palette type with a palette already selected
                try:
                    logger.info(f"Switching to user palette: {user_palette_name}")
                    palette = load_user_palette(user_palette_name)
                    on_palette_change_func(palette, "user", user_palette_name)
                    logger.info(f"Switched to user palette: {user_palette_name}")
                    return {"type": "user", "name": user_palette_name}, counter + 1
                except Exception as e:
                    logger.error(f"Error loading user palette '{user_palette_name}': {e}")
                    raise PreventUpdate

            elif triggered_id == "user-palette-selector" and user_palette_name:
                # User selected a different user palette from dropdown
                try:
                    logger.info(f"Switching to user palette: {user_palette_name}")
                    palette = load_user_palette(user_palette_name)
                    on_palette_change_func(palette, "user", user_palette_name)
                    logger.info(f"Switched to user palette: {user_palette_name}")
                    return {"type": "user", "name": user_palette_name}, counter + 1
                except Exception as e:
                    logger.error(f"Error loading user palette '{user_palette_name}': {e}")
                    raise PreventUpdate

            # No valid change
            raise PreventUpdate

        except Exception as e:
            logger.error(f"Error in apply_selected_palette: {e}")
            raise PreventUpdate

    @callback(
        Output("save-palette-status", "children"),
        Input("save-current-palette-btn", "n_clicks"),
        State("settings-palette-applied", "data"),
        prevent_initial_call=True,
    )
    def save_current_palette(
        n_clicks: int | None,
        current_palette_data: dict[str, Any],
    ) -> html.Div:
        """Save edits to the currently active palette."""
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

            # Apply temporary edits to a copy of the palette
            temp_edits = get_temp_color_edits()
            palette = color_manager.get_palette()
            palette_copy = palette.copy()
            for label, color in temp_edits.items():
                palette_copy.update(label, color)

            # Get the palette data from the copy
            palette_data = palette_copy.to_dict()

            # Determine where to save based on current palette type
            palette_type = current_palette_data.get("type", "project")
            palette_name = current_palette_data.get("name")

            if palette_type == "project":
                # Update project's palette with the modified copy
                data_handler.project._palette = palette_copy
                data_handler.project.save_palette()
                message = "✓ Palette saved to project"
            elif palette_type == "user" and palette_name:
                # Save to existing user palette
                save_user_palette(palette_name, palette_data)
                message = f"✓ Palette saved to '{palette_name}'"
            else:
                return html.Div(
                    "✗ Error: No active palette to save to",
                    className="text-danger mt-2",
                )

            # Clear temporary edits after saving
            clear_temp_color_edits()

            # Refresh the palette in the UI by calling on_palette_change
            if palette_type == "project":
                on_palette_change_func(palette_copy, "project", None)
            elif palette_type == "user" and palette_name:
                on_palette_change_func(palette_copy, "user", palette_name)

            logger.info(f"Saved current palette ({palette_type}: {palette_name or 'project'})")
            return html.Div(
                message,
                className="text-success mt-2",
            )
        except Exception as e:
            logger.error(f"Error saving current palette: {e}")
            return html.Div(
                f"✗ Error: {str(e)}",
                className="text-danger mt-2",
            )

    @callback(
        Output("save-palette-status", "children", allow_duplicate=True),
        Input("save-to-project-btn", "n_clicks"),
        prevent_initial_call=True,
    )
    def save_to_project(
        n_clicks: int | None,
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

            # Apply temporary edits to a copy of the palette
            temp_edits = get_temp_color_edits()
            palette = color_manager.get_palette()
            palette_copy = palette.copy()
            for label, color in temp_edits.items():
                palette_copy.update(label, color)

            # Update project's palette with the modified copy
            data_handler.project._palette = palette_copy
            # Save to project
            data_handler.project.save_palette()

            # Clear temporary edits after saving
            clear_temp_color_edits()

            # Refresh the palette in the UI
            on_palette_change_func(palette_copy, "project", None)

            logger.info("Saved palette to project")
            return html.Div(
                "✓ Palette saved to project",
                className="text-success mt-2",
            )
        except Exception as e:
            logger.error(f"Error saving palette to project: {e}")
            return html.Div(
                f"✗ Error: {str(e)}",
                className="text-danger mt-2",
            )

    @callback(
        Output("save-new-palette-name-container", "style"),
        Input("save-to-new-palette-btn", "n_clicks"),
        prevent_initial_call=True,
    )
    def show_new_palette_name_input(n_clicks: int | None) -> dict[str, str]:
        """Show the new palette name input when save to new palette button is clicked."""
        if not n_clicks:
            raise PreventUpdate
        return {"display": "block"}

    @callback(
        Output("save-palette-status", "children", allow_duplicate=True),
        Output("save-new-palette-name-container", "style", allow_duplicate=True),
        Output("save-new-palette-name", "value"),
        Output("user-palette-selector", "options", allow_duplicate=True),
        Output("user-palette-selector", "value", allow_duplicate=True),
        Input("save-to-new-palette-btn", "n_clicks"),
        State("save-new-palette-name", "value"),
        prevent_initial_call=True,
    )
    def save_to_new_palette(
        n_clicks: int | None,
        palette_name: str | None,
    ) -> tuple[html.Div, dict[str, str], str, list[dict[str, str]], str]:
        """Save current palette to a new user palette."""
        if not n_clicks:
            raise PreventUpdate

        # First click shows input, subsequent clicks with valid name save
        if not palette_name or palette_name.strip() == "":
            return (
                html.Div(
                    "⚠ Enter a name for the new palette above",
                    className="text-warning mt-2",
                ),
                {"display": "block"},
                "",
                no_update,  # type: ignore[return-value]
                no_update,  # type: ignore[return-value]
            )

        try:
            color_manager = get_color_manager_func()

            # Apply temporary edits to a copy of the palette
            temp_edits = get_temp_color_edits()
            palette = color_manager.get_palette()
            palette_copy = palette.copy()
            for label, color in temp_edits.items():
                palette_copy.update(label, color)

            # Get the palette data from the copy
            palette_data = palette_copy.to_dict()

            # Save as new user palette
            save_user_palette(palette_name.strip(), palette_data)

            # Clear temporary edits after saving
            clear_temp_color_edits()

            # Refresh the user palette dropdown options
            user_palettes_paths = list_user_palettes()
            user_palettes = [p.stem for p in user_palettes_paths]
            updated_options = [{"label": p, "value": p} for p in user_palettes]

            # Refresh the palette in the UI to switch to the new palette
            on_palette_change_func(palette_copy, "user", palette_name.strip())

            logger.info(f"Saved palette to new user palette: {palette_name}")
            return (
                html.Div(
                    f"✓ Palette saved as '{palette_name.strip()}'",
                    className="text-success mt-2",
                ),
                {"display": "none"},
                "",
                updated_options,
                palette_name.strip(),
            )
        except Exception as e:
            logger.error(f"Error saving new palette: {e}")
            return (
                html.Div(
                    f"✗ Error: {str(e)}",
                    className="text-danger mt-2",
                ),
                {"display": "block"},
                palette_name,
                no_update,  # type: ignore[return-value]
                no_update,  # type: ignore[return-value]
            )

    @callback(
        Output("delete-confirmation-modal", "is_open"),
        Output("delete-confirmation-text", "children"),
        Input("delete-user-palette-btn", "n_clicks"),
        Input("delete-cancel-btn", "n_clicks"),
        State("user-palette-selector", "value"),
        State("delete-confirmation-modal", "is_open"),
        prevent_initial_call=True,
    )
    def toggle_delete_confirmation(
        delete_clicks: int | None,
        cancel_clicks: int | None,
        selected_palette: str | None,
        is_open: bool,
    ) -> tuple[bool, str]:
        """Toggle the delete confirmation modal."""
        if not ctx.triggered_id:
            raise PreventUpdate

        if ctx.triggered_id == "delete-user-palette-btn":
            if not selected_palette:
                raise PreventUpdate
            return (
                True,
                f"Are you sure you want to delete the user palette '{selected_palette}'? This action cannot be undone.",
            )
        else:  # cancel button
            return False, ""

    @callback(
        Output("delete-palette-status", "children"),
        Output("user-palette-selector", "options", allow_duplicate=True),
        Output("user-palette-selector", "value", allow_duplicate=True),
        Output("delete-confirmation-modal", "is_open", allow_duplicate=True),
        Output("settings-palette-applied", "data", allow_duplicate=True),
        Input("delete-confirm-btn", "n_clicks"),
        State("user-palette-selector", "value"),
        State("settings-palette-applied", "data"),
        prevent_initial_call=True,
    )
    def delete_palette(
        confirm_clicks: int | None,
        palette_name: str | None,
        current_palette_data: dict[str, Any],
    ) -> tuple[html.Div, list[dict[str, str]], str | None, bool, dict[str, Any]]:
        """Delete the selected user palette."""
        if not confirm_clicks or not palette_name:
            raise PreventUpdate

        try:
            # Delete the palette file
            delete_user_palette(palette_name)

            # Refresh the user palette dropdown options
            user_palettes_paths = list_user_palettes()
            user_palettes = [p.stem for p in user_palettes_paths]
            updated_options = [{"label": p, "value": p} for p in user_palettes]

            # If the deleted palette was currently active, switch to project palette
            new_palette_data = current_palette_data
            if (
                current_palette_data.get("type") == "user"
                and current_palette_data.get("name") == palette_name
            ):
                # Switch to project palette
                data_handler = get_data_handler_func()
                if data_handler is not None:
                    palette = data_handler.project.palette
                    on_palette_change_func(palette, "project", None)
                    new_palette_data = {"type": "project", "name": None}
                    logger.info(
                        f"Deleted active palette '{palette_name}', switched to project palette"
                    )

            logger.info(f"Deleted user palette: {palette_name}")
            return (
                html.Div(
                    f"✓ Palette '{palette_name}' deleted successfully",
                    className="text-success mt-2",
                ),
                updated_options,
                user_palettes[0] if user_palettes else None,
                False,  # Close modal
                new_palette_data,
            )
        except FileNotFoundError:
            logger.error(f"Palette not found: {palette_name}")
            return (
                html.Div(
                    f"✗ Palette '{palette_name}' not found",
                    className="text-danger mt-2",
                ),
                no_update,  # type: ignore[return-value]
                no_update,  # type: ignore[return-value]
                False,  # Close modal
                no_update,  # type: ignore[return-value]
            )
        except Exception as e:
            logger.error(f"Error deleting palette '{palette_name}': {e}")
            return (
                html.Div(
                    f"✗ Error: {str(e)}",
                    className="text-danger mt-2",
                ),
                no_update,  # type: ignore[return-value]
                no_update,  # type: ignore[return-value]
                False,  # Close modal
                no_update,  # type: ignore[return-value]
            )

    # JSON Editor Callbacks
    @callback(
        Output("json-editor-collapse", "is_open"),
        Output("toggle-json-editor-btn", "children"),
        Input("toggle-json-editor-btn", "n_clicks"),
        State("json-editor-collapse", "is_open"),
        prevent_initial_call=True,
    )
    def toggle_json_editor(n_clicks: int | None, is_open: bool) -> tuple[bool, list[Any]]:
        """Toggle the JSON editor collapse."""
        if not n_clicks:
            raise PreventUpdate

        new_state = not is_open
        icon_class = "bi bi-chevron-up me-2" if new_state else "bi bi-chevron-down me-2"
        text = "Hide JSON Editor" if new_state else "Show JSON Editor"

        return new_state, [html.I(className=icon_class), text]

    @callback(
        Output("palette-json-editor", "value"),
        Input("json-editor-collapse", "is_open"),
        Input("reset-json-btn", "n_clicks"),
        prevent_initial_call=True,
    )
    def populate_json_editor(is_open: bool, reset_clicks: int | None) -> str:
        """Populate the JSON editor with current palette data."""
        if not is_open and not reset_clicks:
            raise PreventUpdate

        color_manager = get_color_manager_func()
        if color_manager is None:
            return "{}"

        # Get current palette including any temporary edits
        palette = color_manager.get_palette()
        temp_edits = get_temp_color_edits()

        # Apply temp edits to get the current state
        for label, color in temp_edits.items():
            palette.update(label, color)

        # Get the palette as a dict
        palette_dict = palette.to_dict()

        # Format as pretty JSON
        return json.dumps(palette_dict, indent=2)

    @callback(
        Output("json-editor-status", "children"),
        Output("settings-palette-applied", "data", allow_duplicate=True),
        Output("color-edits-counter", "data", allow_duplicate=True),
        Input("apply-json-btn", "n_clicks"),
        State("palette-json-editor", "value"),
        State("color-edits-counter", "data"),
        State("settings-palette-applied", "data"),
        prevent_initial_call=True,
    )
    def apply_json_palette(
        n_clicks: int | None,
        json_text: str,
        counter: int,
        current_palette_data: dict[str, Any],
    ) -> tuple[html.Div, dict[str, Any], int]:
        """Apply the JSON palette to the color manager."""
        if not n_clicks:
            raise PreventUpdate

        try:
            # Parse the JSON
            palette_dict = json.loads(json_text)

            # Validate structure
            if not isinstance(palette_dict, dict):
                return (
                    html.Div(
                        "✗ Invalid JSON: must be an object/dictionary",
                        className="text-danger mt-2",
                    ),
                    no_update,  # type: ignore[return-value]
                    no_update,  # type: ignore[return-value]
                )

            # Check if it has the expected structure
            if not all(key in palette_dict for key in ["scenarios", "model_years", "metrics"]):
                return (
                    html.Div(
                        "✗ Invalid palette structure: must have 'scenarios', 'model_years', and 'metrics' keys",
                        className="text-danger mt-2",
                    ),
                    no_update,  # type: ignore[return-value]
                    no_update,  # type: ignore[return-value]
                )

            # Create a ColorPalette from the JSON
            palette = ColorPalette(palette_dict)

            # Apply it to the color manager
            on_palette_change_func(palette, "custom", None)

            # Clear temporary edits since we're applying a whole new palette
            clear_temp_color_edits()

            logger.info("Applied palette from JSON editor")
            return (
                html.Div(
                    "✓ JSON palette applied successfully",
                    className="text-success mt-2",
                ),
                {"type": "custom", "name": "JSON Editor"},
                counter + 1,
            )

        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            return (
                html.Div(
                    f"✗ Invalid JSON: {str(e)}",
                    className="text-danger mt-2",
                ),
                no_update,  # type: ignore[return-value]
                no_update,  # type: ignore[return-value]
            )
        except Exception as e:
            logger.error(f"Error applying JSON palette: {e}")
            return (
                html.Div(
                    f"✗ Error: {str(e)}",
                    className="text-danger mt-2",
                ),
                no_update,  # type: ignore[return-value]
                no_update,  # type: ignore[return-value]
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
