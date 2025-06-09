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

    raise ValueError(f"Not a valid rgb(a) string {rgba_str}")
