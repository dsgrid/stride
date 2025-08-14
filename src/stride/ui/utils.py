from functools import lru_cache
from typing import Iterable, Callable
from itertools import cycle
from plotly import colors
import re


def create_color_generator(
    initial_keys: list | None = None,
    color_pallette: Iterable[str] = colors.qualitative.Dark24,
) -> Callable[[str], str]:
    color_iterator = cycle(color_pallette)

    @lru_cache
    def color_generator(key: str):
        hex_color = next(color_iterator)
        rgba = rgba_to_str(*hex_to_rgba(hex_color))
        return rgba

    if initial_keys:
        for key in initial_keys:
            _ = color_generator(key)

    return color_generator


def hex_to_rgba(hex_color) -> tuple[int, int, int, float]:
    """Converts a hex color code to an RGB tuple.

    Args:
        hex_color: A string representing the hex color code, with or without the '#' prefix.

    Returns:
        A tuple of three integers representing the RGB values (0-255).
    """
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore


def rgba_to_str(r: int, g: int, b: int, a: float = 1.0) -> str:
    return f"rgba({r}, {g}, {b}, {a})"


def str_to_rgba(rgba_str: str) -> tuple[int, int, int, float]:
    rgba = re.search(r"rgba\((\d+), (\d+), (\d+), ([\d\.]+)\)", rgba_str)
    if rgba is not None:
        return (
            int(rgba.groups()[0]),
            int(rgba.groups()[1]),
            int(rgba.groups()[2]),
            float(rgba.groups()[3]),
        )  # type: ignore

    rgb = re.search(r"rgba\((\d+), (\d+), (\d+)\)", rgba_str)
    if rgb is not None:
        return tuple(*rgb.groups(), *(1))  # type: ignore

    verr = f"Not a valid rgb(a) string {rgba_str}"
    raise ValueError(verr)


def create_scenario_colors(
    scenarios: list[str], color_generator: Callable[[str], str]
) -> dict[str, dict[str, str]]:
    """
    Create background and border colors for scenario checkboxes.

    Parameters
    ----------
    scenarios : list[str]
        List of scenario names
    color_generator : Callable[[str], str]
        Function that generates rgba colors for scenarios

    Returns
    -------
    dict[str, dict[str, str]]
        Dictionary with scenario names as keys and color info as values

    Examples
    --------
    >>> scenarios = ["baseline", "high_growth"]
    >>> colors = create_scenario_colors(scenarios, color_gen)
    >>> print(colors)
    {
        "baseline": {
            "bg": "rgba(31, 119, 180, 0.2)",
            "border": "rgba(31, 119, 180, 0.8)"
        },
        "high_growth": {
            "bg": "rgba(255, 127, 14, 0.2)",
            "border": "rgba(255, 127, 14, 0.8)"
        }
    }
    """
    scenario_colors = {}

    for scenario in scenarios:
        base_color = color_generator(scenario)
        r, g, b, _ = str_to_rgba(base_color)

        scenario_colors[scenario] = {
            "bg": rgba_to_str(r, g, b, 0.2),
            "border": rgba_to_str(r, g, b, 0.8),
        }

    return scenario_colors


def generate_scenario_css(scenario_colors: dict[str, dict[str, str]]) -> str:
    """
    Generate CSS string for scenario checkbox styling.

    Parameters
    ----------
    scenario_colors : dict[str, dict[str, str]]
        Dictionary of scenario colors from create_scenario_colors()

    Returns
    -------
    str
        CSS string with scenario-specific styling rules
    """
    css_rules = []

    for scenario, scolors in scenario_colors.items():
        # Escape scenario name for CSS selector (replace spaces, special chars)
        escaped_scenario = scenario.replace(" ", "\\ ").replace("(", "\\(").replace(")", "\\)")

        css_rule = f"""
        .scenario-checklist .form-check-input[value='{escaped_scenario}']:checked + .form-check-label {{
            background-color: {scolors['bg']} !important;
            border-color: {scolors['border']} !important;
        }}"""
        css_rules.append(css_rule)

    return "\n".join(css_rules)
