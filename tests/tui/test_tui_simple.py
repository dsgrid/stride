#!/usr/bin/env python3
"""
Simple test to verify TUI rendering works correctly.
"""

from rich.style import Style
from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import DataTable, Footer, Header, Label


class SimpleTestApp(App[None]):
    """Simple test app to verify DataTable works."""

    CSS = """
    Screen {
        background: $surface;
    }

    .test-column {
        width: 1fr;
        height: 100%;
        margin: 1;
        padding: 1;
        background: $panel;
        border: solid $accent;
    }

    DataTable {
        height: 1fr;
    }
    """

    BINDINGS = [("q", "quit", "Quit")]

    def compose(self) -> ComposeResult:
        """Compose the UI."""
        yield Header(show_clock=True)
        yield Label("Testing DataTable Display")

        with Horizontal():
            with Vertical(classes="test-column"):
                yield Label("[bold cyan]Test Group 1[/bold cyan]")
                yield DataTable(id="table1")

            with Vertical(classes="test-column"):
                yield Label("[bold cyan]Test Group 2[/bold cyan]")
                yield DataTable(id="table2")

        yield Footer()

    def on_mount(self) -> None:
        """Populate tables after mounting."""
        # Table 1
        table1 = self.query_one("#table1", DataTable)
        table1.add_columns("Label", "Color", "Preview")
        table1.cursor_type = "row"

        test_data_1 = {
            "residential": "#5F4690",
            "commercial": "#FF5733",
            "industrial": "#3498DB",
        }

        for label, color in test_data_1.items():
            preview = Text("████", style=Style(color=color))
            table1.add_row(label, color, preview)

        # Table 2
        table2 = self.query_one("#table2", DataTable)
        table2.add_columns("Year", "Value")
        table2.cursor_type = "row"

        test_data_2 = {
            "2025": "rgb(237, 173, 8)",
            "2030": "rgb(204, 80, 62)",
            "2035": "rgb(111, 64, 112)",
        }

        for year, color in test_data_2.items():
            preview = Text("████", style=Style(color=color))
            table2.add_row(year, preview)


if __name__ == "__main__":
    app = SimpleTestApp()
    app.run()
