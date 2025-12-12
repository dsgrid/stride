"""
TUI (Text User Interface) framework for managing color palettes in Stride.

This module provides a terminal-based interface for viewing and managing color palettes
at both the user and project levels. It uses the Textual library to create an interactive
interface with multiple columns for different label groups.
"""

import re
from pathlib import Path
from typing import Any

from loguru import logger
from rich.style import Style
from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, ScrollableContainer
from textual.widgets import DataTable, Footer, Header, Input, Label, Static

from stride.ui.palette import ColorPalette, hex_color_pattern


def color_to_rich_format(color: str) -> str:
    """Convert color string to Rich-compatible format.

    Rich doesn't support rgba() format, so we need to convert it.

    Parameters
    ----------
    color : str
        Color string in hex, rgb, or rgba format

    Returns
    -------
    str
        Color string that Rich can parse
    """
    # If it's rgba, convert to rgb by dropping the alpha
    if color.startswith("rgba("):
        # Extract rgb values only
        match = re.match(r"rgba?\((\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*[\d.]+)?\)", color)
        if match:
            r, g, b = match.groups()
            return f"rgb({r},{g},{b})"
    return color


def validate_color(color: str) -> bool:
    """Validate if the color string is in a valid format.

    Parameters
    ----------
    color : str
        Color string to validate

    Returns
    -------
    bool
        True if valid, False otherwise
    """
    if not color:
        return False

    # Check hex format
    if hex_color_pattern.match(color):
        return True

    # Check rgb/rgba format
    rgb_pattern = re.compile(r"^rgba?\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*(?:,\s*[\d.]+\s*)?\)$")
    if rgb_pattern.match(color):
        return True

    return False


class PaletteInfo(Static):
    """Widget to display palette metadata (name, location)."""

    def __init__(self, name: str, location: Path, palette_type: str, **kwargs: Any) -> None:
        """Initialize the palette info widget.

        Parameters
        ----------
        name : str
            Name of the palette (derived from filename)
        location : Path
            Full path to the palette file
        palette_type : str
            Type of palette ('user' or 'project')
        """
        super().__init__(**kwargs)
        self.palette_name = name
        self.palette_location = location
        self.palette_type = palette_type

    def compose(self) -> ComposeResult:
        """Compose the palette info display."""
        info_text = (
            f"[bold cyan]Palette:[/bold cyan] {self.palette_name}  |  "
            f"[bold cyan]Type:[/bold cyan] {self.palette_type}  |  "
            f"[bold cyan]Location:[/bold cyan] {self.palette_location}"
        )
        yield Label(info_text)


class LabelGroupColumn(Static):
    """Widget to display a single label group as a column."""

    def __init__(
        self,
        group_name: str,
        labels: dict[str, str],
        parent_viewer: "PaletteViewer",
        **kwargs: Any,
    ) -> None:
        """Initialize a label group column.

        Parameters
        ----------
        group_name : str
            Name of the label group (e.g., "End Uses", "Scenarios")
        labels : dict[str, str]
            Mapping of label names to hex color strings
        parent_viewer : PaletteViewer
            Reference to parent viewer for edit callbacks
        """
        super().__init__(**kwargs)
        self.group_name = group_name
        self.labels = labels
        self.parent_viewer = parent_viewer

    def compose(self) -> ComposeResult:
        """Compose the label group column."""
        # Group header
        yield Label(f"[bold white on blue] {self.group_name} [/bold white on blue]")

        # Create a data table for the labels
        # Use a valid CSS ID (replace spaces and special chars with underscores)
        table_id = f"table_{self.group_name.replace(' ', '_').replace('-', '_')}"
        table: DataTable[Any] = DataTable(zebra_stripes=True, classes="label-table", id=table_id)
        table.cursor_type = "cell"
        table.show_cursor = True
        yield table

    def on_mount(self) -> None:
        """Populate the table after mounting."""
        table_id = f"table_{self.group_name.replace(' ', '_').replace('-', '_')}"
        try:
            table: DataTable[Any] = self.query_one("DataTable", DataTable)
            table.add_columns("Label", "Color", "Preview")

            # Add rows (preserve order from dict - insertion order is maintained in Python 3.7+)
            for label, color in self.labels.items():
                # Create a color preview using the color (convert to Rich-compatible format)
                rich_color = color_to_rich_format(color)
                preview = Text("████", style=Style(color=rich_color))
                table.add_row(label, color, preview)
        except Exception as e:
            logger.error(f"Error populating table {table_id}: {e}")
            raise


class PaletteViewer(App[None]):
    """Main TUI application for viewing and managing color palettes."""

    CSS = """
    Screen {
        background: $surface;
    }

    #palette-info {
        height: auto;
        padding: 1 2;
        margin-bottom: 1;
        background: $panel;
        border: solid $primary;
    }

    #columns-container {
        height: 1fr;
        padding: 1;
        overflow-x: auto;
        overflow-y: auto;
    }

    LabelGroupColumn {
        width: auto;
        min-width: 25;
        max-width: 35;
        height: auto;
        margin: 0 1;
        padding: 1;
        background: $panel;
        border: solid $accent;
    }

    .label-table {
        height: auto;
        min-height: 10;
        max-height: 30;
        margin-top: 1;
    }

    /* Highlight only specific columns, not the preview */
    DataTable > .datatable--cursor {
        background: transparent;
    }

    /* Highlight Label column (column 0) when selected */
    DataTable > .datatable--cursor-cell-0-0 {
        background: $accent 30%;
    }

    /* Highlight Color column (column 1) when selected */
    DataTable > .datatable--cursor-cell-0-1 {
        background: $accent 30%;
    }

    Label {
        margin: 0 0 1 0;
    }

    Horizontal {
        width: auto;
        height: auto;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit", priority=True),
        Binding("e", "edit_color", "Edit"),
        Binding("a", "add_label", "Add Label"),
        Binding("x", "delete_label", "Delete Label"),
        Binding("X", "delete_group", "Delete Group"),
        Binding("s", "save_palette", "Save"),
        Binding("u", "move_up", "Move Up"),
        Binding("d", "move_down", "Move Down"),
        Binding("r", "refresh", "Refresh"),
        ("?", "help", "Help"),
        Binding("escape", "cancel_edit", "Cancel Edit", show=False),
    ]

    def __init__(
        self,
        palette_name: str,
        palette_location: Path,
        palette_type: str,
        label_groups: dict[str, dict[str, str]],
        **kwargs: Any,
    ) -> None:
        """Initialize the palette viewer application.

        Parameters
        ----------
        palette_name : str
            Name of the palette
        palette_location : Path
            Path to the palette file
        palette_type : str
            Type of palette ('user' or 'project')
        label_groups : dict[str, dict[str, str]]
            Nested dictionary of group_name -> label_name -> color
        """
        super().__init__(**kwargs)
        self.palette_name = palette_name
        self.palette_location = palette_location
        self.palette_type = palette_type
        self.label_groups = label_groups
        self.has_unsaved_changes = False
        self.editing_mode = False
        self.editing_table: DataTable[Any] | None = None
        self.editing_row: int | None = None
        self.editing_label: str | None = None
        self.original_color: str | None = None
        self.input_mode: str | None = (
            None  # Tracks what we're inputting: 'edit', 'add_label', 'add_color'
        )
        self.temp_label_name: str | None = None  # Temporary storage for label name when adding
        self.temp_group_name: str | None = (
            None  # Temporary storage for group name when adding labels
        )

    def compose(self) -> ComposeResult:
        """Compose the main UI layout."""
        yield Header(show_clock=True)

        # Palette info section
        yield PaletteInfo(
            self.palette_name,
            self.palette_location,
            self.palette_type,
            id="palette-info",
        )

        # Columns container with horizontal layout
        with ScrollableContainer(id="columns-container"):
            with Horizontal():
                # Create a column for each label group
                # Create a column for each label group
                if self.label_groups:
                    for group_name, labels in self.label_groups.items():
                        yield LabelGroupColumn(group_name, labels, self)
                else:
                    # If palette is empty, show a helpful message
                    yield Label(
                        "[dim]Empty palette. Press 'a' to add a label.[/dim]",
                        id="empty-palette-msg",
                    )

        yield Footer()

    def on_mount(self) -> None:
        """Called when the app is mounted and all widgets are ready."""
        # Focus first table if available
        tables = self.query(DataTable)
        if tables:
            tables.first().focus()

    def action_edit_color(self) -> None:
        """Enter edit mode for the selected color cell."""
        # Find which table has focus
        focused_table = None
        for table in self.query(DataTable):
            if table.has_focus:
                focused_table = table
                break

        if not focused_table:
            self.notify("No color selected. Navigate to a color first.", severity="warning")
            return

        # Make sure we're in the Color column (column 1)
        if focused_table.cursor_column != 1:
            # Move to color column
            focused_table.move_cursor(column=1)

        if focused_table.cursor_row is None or focused_table.cursor_row < 0:
            self.notify("No color selected. Navigate to a color first.", severity="warning")
            return

        row_key = focused_table.get_row_at(focused_table.cursor_row)
        label = str(row_key[0])
        current_color = str(row_key[1])

        # Enter editing mode
        self.editing_mode = True
        self.editing_table = focused_table
        self.editing_row = focused_table.cursor_row
        self.editing_label = label
        self.original_color = current_color

        # Replace the cell with an Input widget
        self.mount_inline_editor(focused_table, current_color)

    def mount_inline_editor(self, table: DataTable[Any], current_color: str) -> None:
        """Mount an inline input widget for editing the color.

        Parameters
        ----------
        table : DataTable
            The table containing the cell to edit
        current_color : str
            The current color value
        """
        # Create an input widget for inline editing
        input_widget = Input(
            value=current_color,
            placeholder="e.g., #FF5733 or rgb(255,87,51)",
            id="inline-color-input",
        )

        # Mount it near the table
        self.mount(input_widget)
        input_widget.focus()

        self.notify("Type new color and press Enter to save, Esc to cancel", timeout=2)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle inline input submission."""
        if event.input.id == "inline-color-input" and self.editing_mode:
            new_color = event.value.strip()

            # Validate the color
            if validate_color(new_color):
                self.apply_color_edit(new_color)
                event.input.remove()
                self.editing_mode = False
                if self.editing_table:
                    self.editing_table.focus()
            else:
                self.notify(
                    "Invalid color format. Use hex (#FF5733) or rgb (rgb(255,87,51))",
                    severity="error",
                )
        elif event.input.id == "add-label-input":
            self.handle_add_label_name(event.value.strip(), event.input)
        elif event.input.id == "add-color-input":
            self.handle_add_label_color(event.value.strip(), event.input)

    def action_cancel_edit(self) -> None:
        """Cancel inline editing or input mode."""
        if self.editing_mode:
            input_widget = self.query_one("#inline-color-input", Input)
            input_widget.remove()
            self.editing_mode = False
            if self.editing_table:
                self.editing_table.focus()
            self.notify("Edit cancelled")
        elif self.input_mode:
            # Cancel any other input mode
            input_ids = ["add-label-input", "add-color-input"]
            for input_id in input_ids:
                try:
                    input_widget = self.query_one(f"#{input_id}", Input)
                    input_widget.remove()
                except Exception:
                    pass
            self.input_mode = None
            self.temp_label_name = None
            self.temp_group_name = None
            self.notify("Input cancelled")

    def apply_color_edit(self, new_color: str) -> None:
        """Apply the color edit to the table and data.

        Parameters
        ----------
        new_color : str
            The new color value
        """
        if not self.editing_table or self.editing_row is None or not self.editing_label:
            return

        # Update the label_groups data
        for group_name, labels in self.label_groups.items():
            if self.editing_label in labels:
                labels[self.editing_label] = new_color
                self.has_unsaved_changes = True

                # Refresh the table to show the updated color
                self._refresh_table(self.editing_table, group_name)

                self.label_groups[group_name][self.editing_label] = new_color
                self.notify(f"Updated {self.editing_label} to {new_color}")
                break

    def action_add_label(self) -> None:
        """Add a new label to the currently focused group."""
        if self.editing_mode or self.input_mode:
            return

        # Find which table has focus (or which group to add to)
        group_name = None

        for table in self.query(DataTable):
            if table.has_focus:
                # Find the parent column to get the group name
                parent_column = table.parent
                while parent_column and not isinstance(parent_column, LabelGroupColumn):
                    parent_column = parent_column.parent
                if parent_column:
                    group_name = parent_column.group_name  # type: ignore[attr-defined]
                break

        # If no group is focused and we have groups, ask which group
        # If no groups exist, we need to create one first
        if not group_name:
            if not self.label_groups:
                self.notify(
                    "No groups exist. Cannot add labels to empty palette.", severity="warning"
                )
                return
            # Default to first group
            group_name = list(self.label_groups.keys())[0]
            self.notify(f"No group selected. Adding to '{group_name}'", timeout=2)

        # Prompt for label name
        self.input_mode = "add_label"
        self.temp_group_name = group_name
        input_widget = Input(
            placeholder="Enter label name (e.g., 'Heating', 'Residential')",
            id="add-label-input",
        )
        self.mount(input_widget)
        input_widget.focus()
        self.notify(f"Enter label name for group '{group_name}'", timeout=3)

    def handle_add_label_name(self, label_name: str, input_widget: Input) -> None:
        """Handle the label name input when adding a new label."""
        if not label_name:
            self.notify("Label name cannot be empty", severity="error")
            return

        # Check if label already exists in this group
        group_name = self.temp_group_name
        if group_name and label_name in self.label_groups.get(group_name, {}):
            self.notify(f"Label '{label_name}' already exists in '{group_name}'", severity="error")
            return

        # Store the label name and prompt for color
        self.temp_label_name = label_name
        input_widget.remove()

        # Prompt for color (optional - can press Enter for auto-assigned color)
        self.input_mode = "add_color"
        color_input = Input(
            placeholder="Enter color (e.g., #FF5733) or press Enter for auto-color",
            id="add-color-input",
        )
        self.mount(color_input)
        color_input.focus()
        self.notify("Enter color or press Enter to auto-assign", timeout=3)

    def handle_add_label_color(self, color: str, input_widget: Input) -> None:
        """Handle the color input when adding a new label."""
        group_name = self.temp_group_name
        label_name = self.temp_label_name

        if not group_name or not label_name:
            self.notify("Error: Missing group or label name", severity="error")
            input_widget.remove()
            self.input_mode = None
            return

        # If no color provided, auto-assign from theme using ColorPalette
        if not color:
            # Create a temporary ColorPalette with existing labels to get next color
            temp_palette = ColorPalette(self.label_groups.get(group_name, {}))
            # This will automatically cycle to the next color in the theme
            color = temp_palette.get(label_name)
        elif not validate_color(color):
            self.notify("Invalid color format. Use hex (#FF5733) or rgb format", severity="error")
            return

        # Add the label to the group
        if group_name not in self.label_groups:
            self.label_groups[group_name] = {}

        self.label_groups[group_name][label_name] = color
        self.has_unsaved_changes = True

        # Refresh the display
        self._refresh_display()

        # Clean up
        input_widget.remove()
        self.input_mode = None
        self.temp_label_name = None
        self.temp_group_name = None

        self.notify(f"Added label '{label_name}' to '{group_name}'", severity="information")

    def _refresh_display(self) -> None:
        """Refresh the entire display with updated label groups."""
        # Remove the columns container and rebuild it
        container = self.query_one("#columns-container", ScrollableContainer)

        # Remove all children
        for child in list(container.children):
            child.remove()

        # Create horizontal layout and mount it
        horizontal = Horizontal()
        container.mount(horizontal)

        if self.label_groups:
            # Remove empty palette message if it exists
            try:
                msg = self.query_one("#empty-palette-msg")
                msg.remove()
            except Exception:
                pass

            for group_name, labels in self.label_groups.items():
                column = LabelGroupColumn(group_name, labels, self)
                horizontal.mount(column)
        else:
            # Show empty message
            label = Label(
                "[dim]Empty palette. Press 'c' to create a new group or 'a' to add a label.[/dim]",
                id="empty-palette-msg",
            )
            horizontal.mount(label)

    def action_delete_label(self) -> None:
        """Delete the currently selected label."""
        if self.editing_mode or self.input_mode:
            return

        # Find which table has focus
        focused_table = None
        group_name = None

        for table in self.query(DataTable):
            if table.has_focus:
                focused_table = table
                # Find the parent column to get the group name
                parent_column = table.parent
                while parent_column and not isinstance(parent_column, LabelGroupColumn):
                    parent_column = parent_column.parent
                if parent_column:
                    group_name = parent_column.group_name  # type: ignore[attr-defined]
                break

        if not focused_table or not group_name:
            self.notify("No label selected", severity="warning")
            return

        if focused_table.cursor_row is None or focused_table.cursor_row < 0:
            self.notify("No label selected", severity="warning")
            return

        # Get the label name from the current row
        row_key = focused_table.get_row_at(focused_table.cursor_row)
        label = str(row_key[0])

        # Delete the label from the group
        if group_name in self.label_groups and label in self.label_groups[group_name]:
            del self.label_groups[group_name][label]
            self.has_unsaved_changes = True

            # If group is now empty, optionally remove it (or keep it empty)
            if not self.label_groups[group_name]:
                # Keep the empty group for now - user can delete it with 'X'
                pass

            # Refresh the display
            self._refresh_display()

            self.notify(f"Deleted label '{label}' from '{group_name}'", severity="information")
        else:
            self.notify(f"Label '{label}' not found", severity="error")

    def action_delete_group(self) -> None:
        """Delete the currently focused group/category (disabled for pre-defined groups)."""
        if self.editing_mode or self.input_mode:
            return

        # Find which table has focus to determine the group
        group_name = None

        for table in self.query(DataTable):
            if table.has_focus:
                # Find the parent column to get the group name
                parent_column = table.parent
                while parent_column and not isinstance(parent_column, LabelGroupColumn):
                    parent_column = parent_column.parent
                if parent_column:
                    group_name = parent_column.group_name  # type: ignore[attr-defined]
                break

        if not group_name:
            self.notify("No group selected", severity="warning")
            return

        # Prevent deletion of pre-defined groups
        predefined_groups = {"Scenarios", "Model Years", "Metrics"}
        if group_name in predefined_groups:
            self.notify(
                f"Cannot delete pre-defined group '{group_name}'. You can only delete labels within it.",
                severity="warning",
            )
            return

        # Confirm deletion (since this removes all labels in the group)
        if group_name in self.label_groups:
            label_count = len(self.label_groups[group_name])
            del self.label_groups[group_name]
            self.has_unsaved_changes = True

            # Refresh the display
            self._refresh_display()

            msg = f"Deleted group '{group_name}'"
            if label_count > 0:
                msg += f" and {label_count} label(s)"
            self.notify(msg, severity="information")
        else:
            self.notify(f"Group '{group_name}' not found", severity="error")

    def action_save_palette(self) -> None:
        """Save the current palette to disk."""
        if not self.has_unsaved_changes:
            self.notify("No changes to save")
            return

        try:
            # Convert label_groups to structured format
            # Map display names back to internal names
            display_to_category = {
                "Scenarios": "scenarios",
                "Model Years": "model_years",
                "Metrics": "metrics",
            }

            structured_palette = {
                "scenarios": {},
                "model_years": {},
                "metrics": {},
            }

            for group_name, labels in self.label_groups.items():
                category_name = display_to_category.get(group_name)
                if category_name:
                    structured_palette[category_name] = labels
                else:
                    # Legacy/unknown groups - add to metrics
                    structured_palette["metrics"].update(labels)

            if self.palette_type == "project":
                # Save to project.json5
                from stride.models import ProjectConfig

                config = ProjectConfig.from_file(self.palette_location)
                config.color_palette = structured_palette
                self.palette_location.write_text(config.model_dump_json(indent=2))
                self.notify(
                    f"Saved project palette to {self.palette_location}", severity="information"
                )
            else:
                # Save to user palette JSON
                import json

                data = {
                    "name": self.palette_name,
                    "palette": structured_palette,
                }
                with open(self.palette_location, "w") as f:
                    json.dump(data, f, indent=2)
                self.notify(
                    f"Saved user palette to {self.palette_location}", severity="information"
                )

            self.has_unsaved_changes = False
        except Exception as e:
            self.notify(f"Error saving palette: {e}", severity="error")
            logger.error(f"Error saving palette: {e}")

    def action_move_up(self) -> None:
        """Move the selected item up within its group."""
        if self.editing_mode:
            return

        # Find which table has focus
        focused_table = None
        for table in self.query(DataTable):
            if table.has_focus:
                focused_table = table
                break

        if not focused_table:
            return

        # Get the current cursor position
        cursor_row = focused_table.cursor_row
        if cursor_row <= 0:
            return

        # Find the parent column to get the group name
        parent_column = focused_table.parent
        while parent_column and not isinstance(parent_column, LabelGroupColumn):
            parent_column = parent_column.parent

        if not parent_column:
            return

        group_name = parent_column.group_name  # type: ignore[attr-defined]

        # Convert the group's labels to a list of items
        from stride.ui.palette import ColorPalette

        labels_dict = self.label_groups[group_name]
        items = [
            {"label": label, "color": color, "order": idx}
            for idx, (label, color) in enumerate(labels_dict.items())
        ]

        # Move the item up
        palette = ColorPalette()
        if palette.move_item_up(items, cursor_row):
            # Update the label_groups with new order
            self.label_groups[group_name] = {
                str(item["label"]): str(item["color"]) for item in items
            }

            # Refresh the table
            self._refresh_table(focused_table, group_name)

            # Move cursor to follow the item
            focused_table.move_cursor(row=cursor_row - 1)

            self.has_unsaved_changes = True

    def action_move_down(self) -> None:
        """Move the selected item down within its group."""
        if self.editing_mode:
            return

        # Find which table has focus
        focused_table = None
        for table in self.query(DataTable):
            if table.has_focus:
                focused_table = table
                break

        if not focused_table:
            return

        # Get the current cursor position
        cursor_row = focused_table.cursor_row
        if cursor_row >= focused_table.row_count - 1:
            return

        # Find the parent column to get the group name
        parent_column = focused_table.parent
        while parent_column and not isinstance(parent_column, LabelGroupColumn):
            parent_column = parent_column.parent

        if not parent_column:
            return

        group_name = parent_column.group_name  # type: ignore[attr-defined]

        # Convert the group's labels to a list of items
        from stride.ui.palette import ColorPalette

        labels_dict = self.label_groups[group_name]
        items = [
            {"label": label, "color": color, "order": idx}
            for idx, (label, color) in enumerate(labels_dict.items())
        ]

        # Move the item down
        palette = ColorPalette()
        if palette.move_item_down(items, cursor_row):
            # Update the label_groups with new order
            self.label_groups[group_name] = {
                str(item["label"]): str(item["color"]) for item in items
            }

            # Refresh the table
            self._refresh_table(focused_table, group_name)

            # Move cursor to follow the item
            focused_table.move_cursor(row=cursor_row + 1)

            self.has_unsaved_changes = True

    def _refresh_table(self, table: DataTable[Any], group_name: str) -> None:
        """Refresh a table with updated data from label_groups.

        Parameters
        ----------
        table : DataTable
            The table to refresh
        group_name : str
            The name of the group to refresh from
        """
        # Clear and repopulate the table
        table.clear()
        labels = self.label_groups[group_name]

        for label, color in labels.items():
            # Create a color preview using the color
            rich_color = color_to_rich_format(color)
            preview = Text("████", style=Style(color=rich_color))
            table.add_row(label, color, preview)

    def action_refresh(self) -> None:
        """Refresh the palette display."""
        self.notify("Palette refreshed")

    def action_help(self) -> None:
        """Show help information."""
        help_text = """
Stride Palette Viewer - Keyboard Shortcuts

Navigation:
- Arrow keys: Navigate between cells
- Tab/Shift+Tab: Move between columns

Actions:
- a: Add new label to current group
- e: Edit color (type directly, Enter to save, Esc to cancel)
- x: Delete current label
- X: Delete current group (disabled for pre-defined groups)
- u: Move item up within its group
- d: Move item down within its group
- s: Save changes to disk
- q: Quit
- r: Refresh
- ?: Show this help
- Esc: Cancel current input

Note: Groups (Scenarios, Model Years, Metrics) are pre-defined and cannot be deleted.
"""
        self.notify(help_text, timeout=12)


def organize_palette_by_groups(
    palette: dict[str, str] | dict[str, dict[str, str]],
    project_config: Any | None = None,
) -> dict[str, dict[str, str]]:
    """Organize a palette dictionary into the three pre-defined groups.

    Parameters
    ----------
    palette : dict[str, str] | dict[str, dict[str, str]]
        Either a flat dictionary of label -> color mappings (legacy format) or
        a structured dictionary with 'scenarios', 'model_years', and 'metrics' keys.
    project_config : Any | None, optional
        Optional project configuration (not currently used but kept for compatibility)

    Returns
    -------
    dict[str, dict[str, str]]
        Nested dictionary organized by the three pre-defined groups:
        'Scenarios', 'Model Years', and 'Metrics'
    """
    # Check if it's the new structured format
    if (
        isinstance(palette, dict)
        and "scenarios" in palette
        and "model_years" in palette
        and "metrics" in palette
    ):
        # Use the structured format directly, mapping to display names
        scenarios_dict = palette.get("scenarios", {})
        model_years_dict = palette.get("model_years", {})
        metrics_dict = palette.get("metrics", {})

        # Ensure all values are dicts of strings
        result: dict[str, dict[str, str]] = {
            "Scenarios": scenarios_dict if isinstance(scenarios_dict, dict) else {},
            "Model Years": model_years_dict if isinstance(model_years_dict, dict) else {},
            "Metrics": metrics_dict if isinstance(metrics_dict, dict) else {},
        }
        return result
    else:
        # Legacy flat format - put everything in Metrics for now
        metrics_palette: dict[str, str] = {}
        if isinstance(palette, dict):
            for key, value in palette.items():
                if isinstance(value, str):
                    metrics_palette[key] = value
        return {
            "Scenarios": {},
            "Model Years": {},
            "Metrics": metrics_palette,
        }


def launch_palette_viewer(
    palette_path: Path,
    palette_type: str = "project",
    project_config: Any | None = None,
) -> None:
    """Launch the palette viewer TUI.

    Parameters
    ----------
    palette_path : Path
        Path to the palette file (project.json5 or user palette file)
    palette_type : str, optional
        Type of palette ('user' or 'project'), by default "project"
    project_config : Any | None, optional
        Optional project configuration for better label grouping
    """
    if palette_type == "project":
        # For project palettes, we need to load from the project config
        from stride.models import ProjectConfig

        config = ProjectConfig.from_file(palette_path)
        palette_dict = config.color_palette
        palette_name = config.project_id
    else:
        # For user palettes, load directly (assuming JSON format)
        import json

        with open(palette_path) as f:
            data = json.load(f)
            palette_dict = data.get("palette", data)
            palette_name = palette_path.stem

    # Organize palette into groups
    label_groups = organize_palette_by_groups(palette_dict, project_config)

    # Launch the TUI
    app = PaletteViewer(
        palette_name=palette_name,
        palette_location=palette_path,
        palette_type=palette_type,
        label_groups=label_groups,
    )
    app.run()


def get_user_palette_dir() -> Path:
    """Get the user's palette directory, creating it if necessary.

    Returns
    -------
    Path
        Path to ~/.stride/palettes/
    """
    palette_dir = Path.home() / ".stride" / "palettes"
    palette_dir.mkdir(parents=True, exist_ok=True)
    return palette_dir


def list_user_palettes() -> list[Path]:
    """List all user palettes.

    Returns
    -------
    list[Path]
        List of paths to user palette files
    """
    palette_dir = get_user_palette_dir()
    return sorted(palette_dir.glob("*.json"))


def save_user_palette(name: str, palette: dict[str, str] | dict[str, dict[str, str]]) -> Path:
    """Save a palette to the user's palette directory.

    Parameters
    ----------
    name : str
        Name for the palette (will be used as filename)
    palette : dict[str, str] | dict[str, dict[str, str]]
        Palette dictionary to save (either flat or structured format)

    Returns
    -------
    Path
        Path to the saved palette file
    """
    import json

    palette_dir = get_user_palette_dir()
    palette_path = palette_dir / f"{name}.json"

    data = {
        "name": name,
        "palette": palette,
    }

    with open(palette_path, "w") as f:
        json.dump(data, f, indent=2)

    return palette_path


def load_user_palette(name: str) -> ColorPalette:
    """Load a user palette by name.

    Parameters
    ----------
    name : str
        Name of the palette to load

    Returns
    -------
    ColorPalette
        Loaded color palette

    Raises
    ------
    FileNotFoundError
        If the palette does not exist
    """
    import json

    palette_dir = get_user_palette_dir()
    palette_path = palette_dir / f"{name}.json"

    if not palette_path.exists():
        msg = f"User palette '{name}' not found"
        raise FileNotFoundError(msg)

    with open(palette_path) as f:
        data = json.load(f)
        # Handle both nested {"palette": {...}} and flat {...} structures
        if isinstance(data, dict):
            if "palette" in data:
                palette_dict = data["palette"]
            else:
                palette_dict = data
        else:
            msg = f"Invalid palette format in {name}.json"
            raise ValueError(msg)

    return ColorPalette(palette_dict)


def delete_user_palette(name: str) -> None:
    """Delete a user palette by name.

    Parameters
    ----------
    name : str
        Name of the palette to delete

    Raises
    ------
    FileNotFoundError
        If the palette does not exist
    """
    palette_dir = get_user_palette_dir()
    palette_path = palette_dir / f"{name}.json"

    if not palette_path.exists():
        msg = f"User palette '{name}' not found"
        raise FileNotFoundError(msg)

    palette_path.unlink()


def get_stride_config_dir() -> Path:
    """Get the stride configuration directory, creating it if necessary.

    Returns
    -------
    Path
        Path to ~/.stride/
    """
    config_dir = Path.home() / ".stride"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_stride_config_path() -> Path:
    """Get the stride configuration file path.

    Returns
    -------
    Path
        Path to ~/.stride/config.json
    """
    return get_stride_config_dir() / "config.json"


def load_stride_config() -> dict[str, Any]:
    """Load the stride configuration file.

    Returns
    -------
    dict[str, Any]
        Configuration dictionary, or empty dict if file doesn't exist
    """
    import json

    config_path = get_stride_config_path()
    if not config_path.exists():
        return {}

    with open(config_path) as f:
        result: dict[str, Any] = json.load(f)
        return result


def save_stride_config(config: dict[str, Any]) -> None:
    """Save the stride configuration file.

    Parameters
    ----------
    config : dict[str, Any]
        Configuration dictionary to save
    """
    import json

    config_path = get_stride_config_path()
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)


def set_default_user_palette(name: str | None) -> None:
    """Set the default user palette.

    Parameters
    ----------
    name : str | None
        Name of the user palette to set as default, or None to clear the default
    """
    config = load_stride_config()

    if name is None:
        config.pop("default_user_palette", None)
    else:
        # Verify the palette exists
        palette_dir = get_user_palette_dir()
        palette_path = palette_dir / f"{name}.json"
        if not palette_path.exists():
            msg = f"User palette '{name}' not found at {palette_path}"
            raise FileNotFoundError(msg)
        config["default_user_palette"] = name

    save_stride_config(config)


def get_default_user_palette() -> str | None:
    """Get the default user palette name.

    Returns
    -------
    str | None
        Name of the default user palette, or None if not set
    """
    config = load_stride_config()
    return config.get("default_user_palette")
