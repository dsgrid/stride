"""
Utilities for managing color palettes for the Stride UI.

The :class:`~stride.ui.palette.ColorPalette` class stores colors as hex strings and automatically
supplies new colors. All color inputs are checked for valid hex string representation and new colors are provided
if a color input is invalid.

The class provides a class method to intialize a palette from a dictionary while sanitizing each input entry.
"""

import re
from itertools import cycle
from typing import Any, Mapping, MutableSequence, TypedDict

from plotly import colors

# can have a project color palette, or a user color palette?
# can toggle between project and use color palette?
#
# Might be simplest just to have project color palette and save
# it into the project json file.

hex_color_pattern = re.compile(r"^#[0-9A-Fa-f]{6}$|^#[0-9A-Fa-f]{8}$")
rgb_color_pattern = re.compile(r"^rgba?\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*(?:,\s*[\d.]+\s*)?\)$")


class PaletteItem(TypedDict):
    """Structure for a palette item with label, color, and order."""

    label: str
    color: str
    order: int


class ColorPalette:
    """Represents a color palette for use in the Stride UI.

    Provides methods to update, get, and pop colors by a key entry.
    Keys typically map to label values in a stack chart or chart label.
    """

    def __init__(
        self,
        palette: dict[str, str] | dict[str, dict[str, str]] | None = None,
    ):
        """Initializes a new ColorPalette instance with colors organized by category.

        Parameters
        ----------
        palette : dict[str, str] | dict[str, dict[str, str]] | None, optional
            Either a flat dictionary of label->color mappings (legacy format) or
            a structured dictionary with 'scenarios', 'model_years', and 'metrics' keys.
        """
        # Different themes for each category
        self.scenario_theme = colors.qualitative.Antique  # type: ignore[attr-defined]
        self.model_year_theme = colors.sequential.YlOrRd  # type: ignore[attr-defined]
        self.metric_theme = colors.qualitative.Prism  # type: ignore[attr-defined]

        self._scenario_iterator = cycle(self.scenario_theme)
        self._model_year_iterator = cycle(self.model_year_theme)
        self._metric_iterator = cycle(self.metric_theme)

        # Separate palettes for each category
        self.scenarios: dict[str, str] = {}
        self.model_years: dict[str, str] = {}
        self.metrics: dict[str, str] = {}

        if palette:
            # Check if it's the new structured format
            if (
                isinstance(palette, dict)
                and "scenarios" in palette
                and "model_years" in palette
                and "metrics" in palette
            ):
                # New structured format
                for label, color in palette.get("scenarios", {}).items():
                    self.update(label, color, category="scenarios")
                for label, color in palette.get("model_years", {}).items():
                    self.update(label, color, category="model_years")
                for label, color in palette.get("metrics", {}).items():
                    self.update(label, color, category="metrics")
            else:
                # Legacy flat format - default to metrics
                for label, color in palette.items():
                    self.update(label, color)

    def __str__(self) -> str:
        """Return a string representation of the palette."""
        num_scenarios = len(self.scenarios)
        num_model_years = len(self.model_years)
        num_metrics = len(self.metrics)
        return f"ColorPalette(scenarios={num_scenarios}, model_years={num_model_years}, metrics={num_metrics})"

    def __repr__(self) -> str:
        """Return a detailed string representation of the palette."""
        return self.__str__()

    def update(self, key: str, color: str | None = None, category: str | None = None) -> None:
        """Updates or creates a new color for the given *key* in the specified category.

        Keys are normalized to lowercase for consistent lookups.

        Parameters
        ----------
        key : str
            The lookup key for which to assign or update the color
        color : str | None, optional
            A hex string or rgb/rgba string representation of the color. If ``None`` or invalid, a new color
            is assigned based on the theme.
        category : str | None, optional
            The category to update: 'scenarios', 'model_years', or 'metrics'.
            If None, attempts to determine automatically or defaults to 'metrics'.

        Raises
        ------
        TypeError
            If *key* is not a string.
        ValueError
            If *category* is not a valid category name.
        """

        if not isinstance(key, str):
            msg = "ColorPalette: Key must be a string"
            raise TypeError(msg)

        # Normalize key to lowercase for consistent lookups
        key = key.lower()

        # Determine which palette to update to get the right color iterator
        if category is None:
            # Auto-detect: check if key exists in any category
            if key in self.scenarios:
                category = "scenarios"
            elif key in self.model_years:
                category = "model_years"
            elif key in self.metrics:
                category = "metrics"
            else:
                # Default to metrics for new keys
                category = "metrics"

        # Get color from appropriate theme if not provided or invalid
        if color is None or not isinstance(color, str):
            if category == "scenarios":
                color = next(self._scenario_iterator)
            elif category == "model_years":
                color = next(self._model_year_iterator)
            else:  # metrics
                color = next(self._metric_iterator)
        elif not (hex_color_pattern.match(color) or rgb_color_pattern.match(color)):
            if category == "scenarios":
                color = next(self._scenario_iterator)
            elif category == "model_years":
                color = next(self._model_year_iterator)
            else:  # metrics
                color = next(self._metric_iterator)

        if category == "scenarios":
            self.scenarios[key] = color
        elif category == "model_years":
            self.model_years[key] = color
            # Re-sort to maintain chronological order (but don't reassign colors)
            # This ensures display order is correct without changing existing color assignments
            self.model_years = dict(
                sorted(self.model_years.items(), key=lambda x: int(x[0]) if x[0].isdigit() else 0)
            )
        elif category == "metrics":
            self.metrics[key] = color
        else:
            msg = (
                f"Invalid category: {category}. Must be 'scenarios', 'model_years', or 'metrics'."
            )
            raise ValueError(msg)

    def get(self, key: str, category: str | None = None) -> str:
        """Returns the hex string representation of the color for a given *key*.

        Keys are normalized to lowercase for consistent lookups.
        Searches across all categories (scenarios, model_years, metrics) unless
        a specific category is provided. If *key* does not exist, a new color is
        generated based on the theme, stored in the metrics category, and returned.

        Parameters
        ----------
        key : str
            The lookup key for the color.
        category : str | None, optional
            Specific category to search: 'scenarios', 'model_years', or 'metrics'.
            If None, searches all categories.

        Returns
        -------
        str
            hex string representing the color for a given *key*
        """
        # Normalize key to lowercase for consistent lookups
        key = key.lower()

        color = None

        if category:
            # Search specific category
            if category == "scenarios":
                color = self.scenarios.get(key)
            elif category == "model_years":
                color = self.model_years.get(key)
            elif category == "metrics":
                color = self.metrics.get(key)
        else:
            # Search all categories
            color = self.scenarios.get(key) or self.model_years.get(key) or self.metrics.get(key)

        if color is None:
            # Get the next color from the appropriate theme and store it in metrics by default
            color = next(self._metric_iterator)
            self.metrics[key] = color

        return color

    def pop(self, key: str, category: str | None = None) -> str:
        """Removes the entry from the palette and returns the color string.

        Keys are normalized to lowercase for consistent lookups.

        Parameters
        ----------
        key : str
            The key to remove from the palette
        category : str | None, optional
            Specific category to remove from. If None, searches all categories.

        Returns
        -------
        str
            The color string that was associated with *key*

        Raises
        ------
        KeyError
            If *key* is not present in any category
        """
        # Normalize key to lowercase for consistent lookups
        key = key.lower()

        if category:
            # Remove from specific category
            if category == "scenarios" and key in self.scenarios:
                return self.scenarios.pop(key)
            elif category == "model_years" and key in self.model_years:
                return self.model_years.pop(key)
            elif category == "metrics" and key in self.metrics:
                return self.metrics.pop(key)
        else:
            # Search all categories
            if key in self.scenarios:
                return self.scenarios.pop(key)
            elif key in self.model_years:
                return self.model_years.pop(key)
            elif key in self.metrics:
                return self.metrics.pop(key)

        msg = f"ColorPalette: unable to remove key: {key}"
        raise KeyError(msg)

    @classmethod
    def from_dict(cls, palette: dict[str, str] | dict[str, dict[str, str]]) -> "ColorPalette":
        """
        Loads the color palette from a dictionary representation with sanitization.

        Parameters
        ----------
        palette : dict[str, str] | dict[str, dict[str, str]]
            Either a flat mapping of string keys to hex color strings (legacy format)
            or a structured dictionary with 'scenarios', 'model_years', and 'metrics' keys.

        Returns
        -------
        ColorPalette
            A new :class:`ColorPalette` instance populated with the provided colors.
            Invalid values are replaced by the next available color in the theme. The default
            theme is Plotly's Prism palette.
        """

        new_palette = cls()

        # Check if it's the new structured format
        if (
            isinstance(palette, dict)
            and "scenarios" in palette
            and "model_years" in palette
            and "metrics" in palette
        ):
            # Process each category with appropriate theme
            for category_name, category_dict in palette.items():
                if category_name not in ["scenarios", "model_years", "metrics"]:
                    continue

                # Get appropriate color iterator for this category
                if category_name == "scenarios":
                    color_iterator = cycle(colors.qualitative.Bold)  # type: ignore[attr-defined]
                elif category_name == "model_years":
                    color_iterator = cycle(colors.sequential.YlOrRd)  # type: ignore[attr-defined]
                else:  # metrics
                    color_iterator = cycle(colors.qualitative.Prism)  # type: ignore[attr-defined]

                # Sort model years as integers before processing to ensure proper color gradient
                items = list(category_dict.items())
                if category_name == "model_years":
                    items.sort(key=lambda x: int(x[0]) if x[0].isdigit() else 0)

                for key, color in items:
                    # Normalize key to lowercase
                    normalized_key = key.lower()

                    if not (hex_color_pattern.match(color) or rgb_color_pattern.match(color)):
                        color = next(color_iterator)

                    if category_name == "scenarios":
                        new_palette.scenarios[normalized_key] = color
                    elif category_name == "model_years":
                        new_palette.model_years[normalized_key] = color
                    elif category_name == "metrics":
                        new_palette.metrics[normalized_key] = color
        else:
            # Legacy flat format - default to metrics
            metric_iterator = cycle(colors.qualitative.Prism)  # type: ignore[attr-defined]
            for key, color in palette.items():
                # Normalize key to lowercase
                normalized_key = key.lower()

                if not (hex_color_pattern.match(color) or rgb_color_pattern.match(color)):
                    color = next(metric_iterator)
                new_palette.metrics[normalized_key] = color

        return new_palette

    def refresh_category_colors(self, category: str) -> None:
        """Reassign colors for all items in a category using the correct theme.

        This is useful for fixing palettes that may have been assigned incorrect
        colors or to refresh colors after theme changes.

        Parameters
        ----------
        category : str
            The category to refresh: 'scenarios', 'model_years', or 'metrics'

        Raises
        ------
        ValueError
            If category is not a valid category name

        Examples
        --------
        >>> palette.refresh_category_colors("metrics")
        """
        if category == "scenarios":
            labels = list(self.scenarios.keys())
            self.scenarios.clear()
            for label in labels:
                self.update(label, category="scenarios")
        elif category == "model_years":
            labels = list(self.model_years.keys())
            # Sort model years as integers so earliest gets yellow, latest gets red
            labels.sort(key=lambda x: int(x) if x.isdigit() else 0)
            self.model_years.clear()
            for label in labels:
                self.update(label, category="model_years")
        elif category == "metrics":
            labels = list(self.metrics.keys())
            self.metrics.clear()
            for label in labels:
                self.update(label, category="metrics")
        else:
            msg = (
                f"Invalid category: {category}. Must be 'scenarios', 'model_years', or 'metrics'."
            )
            raise ValueError(msg)

    def get_display_items(
        self, category: str | None = None
    ) -> dict[str, list[tuple[str, str, str]]]:
        """Get palette items formatted for display with proper capitalization.

        Returns tuples of (display_label, lowercase_key, color) for each item.

        Parameters
        ----------
        category : str | None, optional
            Specific category to get: 'scenarios', 'model_years', or 'metrics'.
            If None, returns all categories.

        Returns
        -------
        dict[str, list[tuple[str, str, str]]]
            Dictionary mapping category names to lists of (display_label, key, color) tuples.
            The display_label is capitalized for presentation, while key is the lowercase
            lookup key.

        Examples
        --------
        >>> palette.get_display_items("metrics")
        {'metrics': [('Industrial', 'industrial', 'rgb(95, 70, 144)'), ...]}
        """
        result: dict[str, list[tuple[str, str, str]]] = {}

        def format_items(items_dict: dict[str, str]) -> list[tuple[str, str, str]]:
            """Convert dict items to display tuples."""
            return [(key.capitalize(), key, color) for key, color in items_dict.items()]

        if category is None:
            # Return all categories
            if self.scenarios:
                result["scenarios"] = format_items(self.scenarios)
            if self.model_years:
                result["model_years"] = format_items(self.model_years)
            if self.metrics:
                result["metrics"] = format_items(self.metrics)
        elif category == "scenarios":
            result["scenarios"] = format_items(self.scenarios)
        elif category == "model_years":
            result["model_years"] = format_items(self.model_years)
        elif category == "metrics":
            result["metrics"] = format_items(self.metrics)
        else:
            msg = (
                f"Invalid category: {category}. Must be 'scenarios', 'model_years', or 'metrics'."
            )
            raise ValueError(msg)

        return result

    def to_dict(self) -> dict[str, dict[str, str]]:
        """Serializes the internal palette to a structured dictionary.

        Returns
        -------
        dict[str, dict[str, str]]
            A dictionary with 'scenarios', 'model_years', and 'metrics' keys,
            each containing a mapping of labels to corresponding hex color strings.
        """
        return {
            "scenarios": self.scenarios.copy(),
            "model_years": self.model_years.copy(),
            "metrics": self.metrics.copy(),
        }

    def to_flat_dict(self) -> dict[str, str]:
        """Serializes the internal palette to a flat dictionary (all categories combined).

        Returns
        -------
        dict[str, str]
            A flat mapping of all labels to corresponding hex color strings.
        """
        result = {}
        result.update(self.scenarios)
        result.update(self.model_years)
        result.update(self.metrics)
        return result

    def move_item_up(self, items: MutableSequence[dict[str, Any]], index: int) -> bool:
        """Move an item up in the list (swap with previous item).

        Parameters
        ----------
        items : MutableSequence[dict[str, Any]]
            The list of palette items to reorder
        index : int
            The index of the item to move up

        Returns
        -------
        bool
            True if the item was moved, False if it was already at the top
        """
        if index > 0:
            items[index - 1], items[index] = items[index], items[index - 1]
            # Update order values
            items[index - 1]["order"], items[index]["order"] = (
                items[index]["order"],
                items[index - 1]["order"],
            )
            return True
        return False

    def move_item_down(self, items: MutableSequence[dict[str, Any]], index: int) -> bool:
        """Move an item down in the list (swap with next item).

        Parameters
        ----------
        items : MutableSequence[dict[str, Any]]
            The list of palette items to reorder
        index : int
            The index of the item to move down

        Returns
        -------
        bool
            True if the item was moved, False if it was already at the bottom
        """
        if index < len(items) - 1:
            items[index], items[index + 1] = items[index + 1], items[index]
            # Update order values
            items[index]["order"], items[index + 1]["order"] = (
                items[index + 1]["order"],
                items[index]["order"],
            )
            return True
        return False

    @staticmethod
    def palette_to_grouped_items(
        palette: dict[str, dict[str, str]],
    ) -> dict[str, list[dict[str, Any]]]:
        """Convert a structured palette into a dict of lists of items.

        Parameters
        ----------
        palette : dict[str, dict[str, str]]
            Structured palette with 'scenarios', 'model_years', 'metrics' categories

        Returns
        -------
        dict[str, list[dict[str, Any]]]
            Dictionary mapping category names to lists of PaletteItems with order
        """
        result: dict[str, list[dict[str, Any]]] = {}

        # Map internal names to display names
        category_display_names = {
            "scenarios": "Scenarios",
            "model_years": "Model Years",
            "metrics": "Metrics",
        }

        for category_name in ["scenarios", "model_years", "metrics"]:
            category_dict = palette.get(category_name, {})
            if category_dict:
                items: list[dict[str, Any]] = []
                for order, (label, color) in enumerate(category_dict.items()):
                    items.append({"label": label, "color": color, "order": order})
                display_name = category_display_names.get(category_name, category_name)
                result[display_name] = items

        return result

    @staticmethod
    def grouped_items_to_palette(
        grouped_items: Mapping[str, list[dict[str, Any]]],
    ) -> dict[str, dict[str, str]]:
        """Convert a structured dict of lists of items back to a palette.

        Parameters
        ----------
        grouped_items : Mapping[str, list[dict[str, Any]]]
            Dictionary mapping group names to lists of PaletteItems

        Returns
        -------
        dict[str, dict[str, str]]
            Structured palette with 'scenarios', 'model_years', 'metrics' categories
        """
        # Map display names back to internal names
        display_to_category = {
            "Scenarios": "scenarios",
            "Model Years": "model_years",
            "Metrics": "metrics",
        }

        palette: dict[str, dict[str, str]] = {
            "scenarios": {},
            "model_years": {},
            "metrics": {},
        }

        for display_name, items in grouped_items.items():
            category_name = display_to_category.get(display_name)
            if category_name:
                # Sort by order to maintain user-defined ordering
                sorted_items = sorted(items, key=lambda x: x["order"])
                for item in sorted_items:
                    palette[category_name][item["label"]] = item["color"]

        return palette
