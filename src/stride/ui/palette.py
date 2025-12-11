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

    def __init__(self, palette: dict[str, str] | None = None):
        """Initializes a new ColorPalette instance with an empty set of colors."""
        # it would be nice to allow the user to set the theme via string, but it seems
        # like that would require a rather large and tedious match block for the dozens of available themes.
        self.theme = colors.qualitative.Prism  # type: ignore[attr-defined]
        self._color_iterator = cycle(self.theme)

        self.palette: dict[str, str] = {}  # color palettes
        if palette:
            for label, color in palette.items():
                self.update(label, color)

    def update(self, key: str, color: str | None = None) -> None:
        """Updates or creates a new color for the given *key*

        Parameters
        ----------
        key : str
            The lookup key for which to assign or update the color
        color : str | None, optional
            A hex string or rgb/rgba string representation of the color. If ``None`` or invalid, a new color
            is assigned based on the theme.

        Raises
        ------
        TypeError
            If *key* is not a string.
        """

        if not isinstance(key, str):
            msg = "ColorPalette: Key must be a string"
            raise TypeError(msg)

        if color is None or not isinstance(color, str):
            color = next(self._color_iterator)
        elif not (hex_color_pattern.match(color) or rgb_color_pattern.match(color)):
            color = next(self._color_iterator)

        self.palette[key] = color

    def get(self, key: str) -> str:
        """Returns the hex string representation of the color for a given *key*

        If *key* does not exist, a new color is generated based on the theme, stored
        and returned.

        Parameters
        ----------
        key
            The lookup key for the color.

        Returns
        -------
        str
            hex string representing the color for a given *key*
        """

        color = self.palette.get(key, None)

        if color is None:
            # Get the next color from the cycle and store it directly
            color = next(self._color_iterator)
            self.palette[key] = color

        return color

    def pop(self, key: str) -> str:
        """Removes the entry from the palette and returns the color string

        Parameters
        ----------
        key : str
            The key to remove from the palette

        Returns
        -------
        str
            The color string that was associated with *key*

        Raises
        ------
        KeyError
            If *key* is not present in the palette
        """
        if key not in self.palette:
            msg = f"ColorPalette: unable to remove key: {key}"
            raise KeyError(msg)

        return self.palette.pop(key)

    @classmethod
    def from_dict(
        cls, palette: dict[str, str]
    ) -> "ColorPalette":  # May want to return bool to show success?
        """
        Loads the color palette from a dictionary representation
        with sanitization.

        Parameters
        ----------
        palette : dict[str, str]
            A mapping of string keys to hex color strings

        Returns
        -------
        ColorPalette
            A new :class:`ColorPalette` instance populated with the provided colors.
            Invalid values are replaced by the next available color in the theme. The default
            theme is Plotly's Prism palette.
        """

        new_palette = cls()
        color_iterator = cycle(colors.qualitative.Prism)  # type: ignore[attr-defined]

        # Want to validate every color value, but don't break if some are not valid colors.
        for key, color in palette.items():
            if not (hex_color_pattern.match(color) or rgb_color_pattern.match(color)):
                color = next(color_iterator)

            new_palette.palette[key] = color

        return new_palette

    def to_dict(self) -> dict[str, str]:
        """Serializes the internal palette to a plain dictionary

        Returns
        -------
        dict
            A copy mapping of labels to corresponding hex color strings.
        """
        return self.palette.copy()

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
        palette: dict[str, str], groups: dict[str, dict[str, str]]
    ) -> dict[str, list[dict[str, Any]]]:
        """Convert a flat palette and groups into a structured dict of lists of items.

        Parameters
        ----------
        palette : dict[str, str]
            Flat dictionary of label -> color mappings
        groups : dict[str, dict[str, str]]
            Grouped palette (e.g., from organize_palette_by_groups)

        Returns
        -------
        dict[str, list[dict[str, Any]]]
            Dictionary mapping group names to lists of PaletteItems with order
        """
        result: dict[str, list[dict[str, Any]]] = {}
        for group_name, group_palette in groups.items():
            items: list[dict[str, Any]] = []
            for order, (label, color) in enumerate(group_palette.items()):
                items.append({"label": label, "color": color, "order": order})
            result[group_name] = items
        return result

    @staticmethod
    def grouped_items_to_palette(
        grouped_items: Mapping[str, list[dict[str, Any]]],
    ) -> dict[str, str]:
        """Convert a structured dict of lists of items back to a flat palette.

        Parameters
        ----------
        grouped_items : Mapping[str, list[dict[str, Any]]]
            Dictionary mapping group names to lists of PaletteItems

        Returns
        -------
        dict[str, str]
            Flat dictionary of label -> color mappings
        """
        palette: dict[str, str] = {}
        for group_name, items in grouped_items.items():
            # Sort by order to maintain user-defined ordering
            sorted_items = sorted(items, key=lambda x: x["order"])
            for item in sorted_items:
                palette[item["label"]] = item["color"]
        return palette
