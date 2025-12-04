"""
Utilities for managing color palettes for the Stride UI.

The :class:`~stride.ui.palette.ColorPalette` class stores colors as hex strings and automatically
supplies new colors. All color inputs are checked for valid hex string representation and new colors are provided
if a color input is invalid.

The class provides a class method to intialize a palette from a dictionary while sanitizing each input entry.
"""

import re
from itertools import cycle

from loguru import logger
from plotly import colors

# can have a project color palette, or a user color palette?
# can toggle between project and use color palette?
#
# Might be simplest just to have project color palette and save
# it into the project json file.

hex_color_pattern = re.compile(r"^#[0-9A-Fa-f]{6}$|^#[0-9A-Fa-f]{8}$")


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
            A hex string representation of the color. If ``None`` or invalid, a new color
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

            logger.debug(f"ColorPalette: creating new color: {color} for key: {key}")
        elif not hex_color_pattern.match(color):
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
            if not hex_color_pattern.match(color):
                new_color = next(color_iterator)
                logger.info(
                    f"color: {color} for key: {key} is not a valid hex string. Overriding color with: {new_color}"
                )
                color = new_color

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
