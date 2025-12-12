import re
from typing import Dict, List, Self

from .palette import ColorPalette


class ColorManager:
    """Singleton class to manage colors and styling for scenarios, sectors, and end uses."""

    _instance = None

    def __new__(cls, palette: ColorPalette | None = None) -> Self:
        if cls._instance is None:
            cls._instance = super(ColorManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, palette: ColorPalette | None = None) -> None:
        # If a new palette is provided, update even if already initialized
        if not hasattr(self, "_scenario_colors"):
            self._scenario_colors = {}  # type: Dict[str, Dict[str, str]]

        if palette is not None:
            self._palette = palette
            self._initialized = True
        elif not self._initialized:
            # First initialization without a palette
            self._palette = ColorPalette()
            self._initialized = True

    def initialize_colors(
        self,
        scenarios: List[str],
        sectors: List[str] | None = None,
        end_uses: List[str] | None = None,
    ) -> None:
        """Initialize colors for all entities at once to ensure consistency."""
        all_keys = scenarios.copy()
        if sectors:
            all_keys.extend(sectors)
        if end_uses:
            all_keys.extend(end_uses)

        # Pre-generate colors for all keys to ensure consistent assignment
        for key in all_keys:
            self.get_color(key)

        # Generate scenario styling colors
        self._generate_scenario_colors(scenarios)

    def get_color(self, key: str) -> str:
        """Get consistent RGBA color for a given key."""
        # Get color from palette (could be hex or rgb string)
        color = self._palette.get(key)

        # Convert to RGBA for UI usage
        if color.startswith("#"):
            return self._hex_to_rgba_str(color)
        elif color.startswith("rgb"):
            # Already in rgb format, ensure it's rgba
            if color.startswith("rgba"):
                return color
            else:
                # Convert rgb to rgba
                return color.replace("rgb(", "rgba(").replace(")", ", 1.0)")
        else:
            # Unknown format, return as is
            return color

    def get_scenario_styling(self, scenario: str) -> Dict[str, str]:
        """Get background and border colors for scenario checkboxes."""
        return self._scenario_colors.get(scenario, {})

    def get_all_scenario_styling(self) -> Dict[str, Dict[str, str]]:
        """Get all scenario styling colors."""
        return self._scenario_colors.copy()

    def generate_scenario_css(self) -> str:
        """Generate CSS string for scenario checkbox styling."""
        css_rules = []

        for scenario, scolors in self._scenario_colors.items():
            # Escape scenario name for CSS selector
            escaped_scenario = scenario.replace(" ", "\\ ").replace("(", "\\(").replace(")", "\\)")

            css_rule = f"""
            .scenario-checklist .form-check-input[value='{escaped_scenario}']:checked + .form-check-label {{
                background-color: {scolors["bg"]} !important;
                border-color: {scolors["border"]} !important;
            }}"""
            css_rules.append(css_rule)

        return "\n".join(css_rules)

    def get_palette(self) -> ColorPalette:
        """Get the underlying ColorPalette instance."""
        return self._palette

    def _generate_scenario_colors(self, scenarios: List[str]) -> None:
        """Generate background and border colors for scenarios."""
        for scenario in scenarios:
            base_color = self.get_color(scenario)
            r, g, b, _ = self._str_to_rgba(base_color)

            self._scenario_colors[scenario] = {
                "bg": self._rgba_to_str(r, g, b, 0.2),
                "border": self._rgba_to_str(r, g, b, 0.8),
            }

    def _hex_to_rgba_str(self, hex_color: str) -> str:
        """Convert hex color to RGBA string.

        Parameters
        ----------
        hex_color : str
            Hex color string starting with #

        Returns
        -------
        str
            RGBA color string
        """
        hex_color = hex_color.lstrip("#")
        r, g, b = tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))
        return self._rgba_to_str(r, g, b, 1.0)

    def _rgba_to_str(self, r: int, g: int, b: int, a: float = 1.0) -> str:
        """Convert RGBA values to string."""
        return f"rgba({r}, {g}, {b}, {a})"

    def _str_to_rgba(self, rgba_str: str) -> tuple[int, int, int, float]:
        """Parse RGBA string to tuple."""
        # Allow optional spaces after commas
        rgba = re.search(r"rgba\((\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*([\d\.]+)\)", rgba_str)
        if rgba is not None:
            return (
                int(rgba.groups()[0]),
                int(rgba.groups()[1]),
                int(rgba.groups()[2]),
                float(rgba.groups()[3]),
            )

        rgb = re.search(r"rgb\((\d+)\s*,\s*(\d+)\s*,\s*(\d+)\)", rgba_str)
        if rgb is not None:
            return (int(rgb.groups()[0]), int(rgb.groups()[1]), int(rgb.groups()[2]), 1.0)

        err = f"Not a valid rgb(a) string {rgba_str}"
        raise ValueError(err)


# Convenience function to get the singleton instance
def get_color_manager(palette: ColorPalette | None = None) -> ColorManager:
    """Get the ColorManager singleton instance.

    Parameters
    ----------
    palette : ColorPalette | None
        Optional ColorPalette to use. Only used on first initialization.
    """
    return ColorManager(palette)
