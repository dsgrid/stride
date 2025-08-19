from typing import Dict, List, Self
from itertools import cycle
from plotly import colors
import re


class ColorManager:
    """Singleton class to manage colors and styling for scenarios, sectors, and end uses."""

    _instance = None

    def __new__(cls) -> Self:
        if cls._instance is None:
            cls._instance = super(ColorManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return

        self._color_palette = colors.qualitative.Prism  # type: ignore[attr-defined]
        self._color_iterator = cycle(self._color_palette)
        self._color_cache: Dict[str, str] = {}
        self._scenario_colors: Dict[str, Dict[str, str]] = {}
        self._initialized: bool = True

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
        if key not in self._color_cache:
            color = next(self._color_iterator)

            # TODO might want to handle all cases with match statement.
            if isinstance(color, str) and color.startswith("#"):
                self._color_cache[key] = self._hex_to_rgba_str(color)
            else:
                # Assume it is already an rgb(a) string
                self._color_cache[key] = color
        return self._color_cache[key]

    def get_scenario_styling(self, scenario: str) -> Dict[str, str]:
        """Get background and border colors for scenario checkboxes."""
        return self._scenario_colors.get(scenario, {})

    def get_all_scenario_styling(self) -> Dict[str, Dict[str, str]]:
        """Get all scenario styling colors."""
        return self._scenario_colors.copy()

    # FIXME This doesn't seem to override the default css for the checkbox as intended
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
        """Convert hex color to RGBA string."""
        hex_color = hex_color.lstrip("#")
        r, g, b = tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))
        return self._rgba_to_str(r, g, b, 1.0)

    def _rgba_to_str(self, r: int, g: int, b: int, a: float = 1.0) -> str:
        """Convert RGBA values to string."""
        return f"rgba({r}, {g}, {b}, {a})"

    def _str_to_rgba(self, rgba_str: str) -> tuple[int, int, int, float]:
        """Parse RGBA string to tuple."""
        rgba = re.search(r"rgba\((\d+), (\d+), (\d+), ([\d\.]+)\)", rgba_str)
        if rgba is not None:
            return (
                int(rgba.groups()[0]),
                int(rgba.groups()[1]),
                int(rgba.groups()[2]),
                float(rgba.groups()[3]),
            )

        rgb = re.search(r"rgb\((\d+), (\d+), (\d+)\)", rgba_str)
        if rgb is not None:
            return (int(rgb.groups()[0]), int(rgb.groups()[1]), int(rgb.groups()[2]), 1.0)

        err = f"Not a valid rgb(a) string {rgba_str}"
        raise ValueError(err)


# Convenience function to get the singleton instance
def get_color_manager() -> ColorManager:
    """Get the ColorManager singleton instance."""
    return ColorManager()
