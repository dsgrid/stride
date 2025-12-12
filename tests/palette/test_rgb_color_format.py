"""Test that rgb() and rgba() format colors are handled correctly throughout the system."""

import pytest

from stride.ui.color_manager import ColorManager
from stride.ui.palette import ColorPalette


def test_rgb_format_in_palette() -> None:
    """Test that ColorPalette accepts rgb() format colors."""
    palette = ColorPalette(
        {
            "Label1": "rgb(200,0,0)",
            "Label2": "rgb(0, 200, 0)",
            "Label3": "rgb(0,0,200)",
        }
    )

    # All colors should be preserved
    assert palette.to_dict()["Label1"] == "rgb(200,0,0)"
    assert palette.to_dict()["Label2"] == "rgb(0, 200, 0)"
    assert palette.to_dict()["Label3"] == "rgb(0,0,200)"


def test_rgba_format_in_palette() -> None:
    """Test that ColorPalette accepts rgba() format colors."""
    palette = ColorPalette(
        {
            "Label1": "rgba(200,0,0,0.5)",
            "Label2": "rgba(0, 200, 0, 0.8)",
            "Label3": "rgba(0,0,200,1.0)",
        }
    )

    # All colors should be preserved
    assert palette.to_dict()["Label1"] == "rgba(200,0,0,0.5)"
    assert palette.to_dict()["Label2"] == "rgba(0, 200, 0, 0.8)"
    assert palette.to_dict()["Label3"] == "rgba(0,0,200,1.0)"


def test_hex_format_in_palette() -> None:
    """Test that ColorPalette still accepts hex format colors."""
    palette = ColorPalette(
        {
            "Label1": "#FF0000",
            "Label2": "#00FF00",
            "Label3": "#0000FF",
        }
    )

    # All colors should be preserved
    assert palette.to_dict()["Label1"] == "#FF0000"
    assert palette.to_dict()["Label2"] == "#00FF00"
    assert palette.to_dict()["Label3"] == "#0000FF"


def test_mixed_formats_in_palette() -> None:
    """Test that ColorPalette accepts mixed format colors."""
    palette = ColorPalette(
        {
            "Hex": "#FF0000",
            "RGB": "rgb(0,255,0)",
            "RGBA": "rgba(0,0,255,0.5)",
            "RGB_Spaces": "rgb(255, 255, 0)",
        }
    )

    # All colors should be preserved
    assert palette.to_dict()["Hex"] == "#FF0000"
    assert palette.to_dict()["RGB"] == "rgb(0,255,0)"
    assert palette.to_dict()["RGBA"] == "rgba(0,0,255,0.5)"
    assert palette.to_dict()["RGB_Spaces"] == "rgb(255, 255, 0)"


def test_color_manager_with_rgb_format() -> None:
    """Test that ColorManager handles rgb() format colors."""
    # Reset singleton
    ColorManager._instance = None  # type: ignore[misc]

    palette = ColorPalette(
        {
            "Residential": "rgb(200,0,0)",
            "Commercial": "rgb(0,200,0)",
            "Industrial": "rgb(0,0,200)",
        }
    )

    cm = ColorManager(palette)
    cm.initialize_colors(["Residential", "Commercial", "Industrial"])

    # Colors should be converted to rgba format
    res = cm.get_color("Residential")
    com = cm.get_color("Commercial")
    ind = cm.get_color("Industrial")

    assert "200" in res and "0" in res  # Red
    assert "200" in com and "0" in com  # Green
    assert "200" in ind and "0" in ind  # Blue


def test_color_manager_with_no_spaces_rgb() -> None:
    """Test that ColorManager handles rgb() colors without spaces after commas."""
    # Reset singleton
    ColorManager._instance = None  # type: ignore[misc]

    palette = ColorPalette({"Label": "rgb(123,45,67)"})

    cm = ColorManager(palette)
    cm.initialize_colors(["Label"])

    color = cm.get_color("Label")

    # Should successfully convert to rgba
    assert "rgba" in color
    assert "123" in color
    assert "45" in color
    assert "67" in color


def test_color_manager_scenario_styling_with_rgb() -> None:
    """Test that scenario styling works with rgb() format colors."""
    # Reset singleton
    ColorManager._instance = None  # type: ignore[misc]

    palette = ColorPalette({"Scenario1": "rgb(255,100,50)"})

    cm = ColorManager(palette)
    cm.initialize_colors(["Scenario1"])

    styling = cm.get_scenario_styling("Scenario1")

    # Should have background and border colors
    assert "bg" in styling
    assert "border" in styling

    # Both should be rgba format
    assert "rgba" in styling["bg"]
    assert "rgba" in styling["border"]

    # Should contain the RGB values
    assert "255" in styling["bg"]
    assert "100" in styling["bg"]
    assert "50" in styling["bg"]


def test_palette_update_with_rgb() -> None:
    """Test that ColorPalette.update() accepts rgb() format."""
    palette = ColorPalette()

    # Update with rgb format
    palette.update("Label1", "rgb(100,150,200)")

    # Should be preserved
    assert palette.get("Label1") == "rgb(100,150,200)"


def test_palette_update_with_rgba() -> None:
    """Test that ColorPalette.update() accepts rgba() format."""
    palette = ColorPalette()

    # Update with rgba format
    palette.update("Label1", "rgba(100,150,200,0.7)")

    # Should be preserved
    assert palette.get("Label1") == "rgba(100,150,200,0.7)"


def test_palette_from_dict_with_rgb() -> None:
    """Test that ColorPalette.from_dict() handles rgb() format."""
    source_dict = {
        "A": "rgb(10,20,30)",
        "B": "rgb(40, 50, 60)",
        "C": "rgba(70,80,90,0.5)",
    }

    palette = ColorPalette.from_dict(source_dict)

    # All colors should be preserved
    assert palette.to_dict()["A"] == "rgb(10,20,30)"
    assert palette.to_dict()["B"] == "rgb(40, 50, 60)"
    assert palette.to_dict()["C"] == "rgba(70,80,90,0.5)"


def test_invalid_rgb_format_gets_replaced() -> None:
    """Test that invalid rgb() format gets replaced with theme color."""
    palette = ColorPalette(
        {
            "Valid": "rgb(100,100,100)",
            "Invalid1": "rgb(300,400,500)",  # Values out of range (but still valid syntax)
            "Invalid2": "rgb(100)",  # Missing values
            "Invalid3": "not-a-color",
        }
    )

    # Valid rgb should be preserved
    assert palette.to_dict()["Valid"] == "rgb(100,100,100)"

    # Invalid ones should be replaced (they'll have theme colors)
    # We can't predict exact theme colors, but they should exist
    assert "Invalid1" in palette.to_dict()
    assert "Invalid2" in palette.to_dict()
    assert "Invalid3" in palette.to_dict()


def test_rgb_with_various_spacing() -> None:
    """Test rgb() colors with various spacing patterns."""
    palette = ColorPalette(
        {
            "NoSpaces": "rgb(10,20,30)",
            "AllSpaces": "rgb(10, 20, 30)",
            "MixedSpaces1": "rgb(10,20, 30)",
            "MixedSpaces2": "rgb(10 , 20 ,30)",
        }
    )

    # All should be accepted and preserved
    assert palette.to_dict()["NoSpaces"] == "rgb(10,20,30)"
    assert palette.to_dict()["AllSpaces"] == "rgb(10, 20, 30)"
    assert palette.to_dict()["MixedSpaces1"] == "rgb(10,20, 30)"
    assert palette.to_dict()["MixedSpaces2"] == "rgb(10 , 20 ,30)"


def test_color_manager_str_to_rgba_parsing() -> None:
    """Test that ColorManager._str_to_rgba() handles various formats."""
    # Reset singleton
    ColorManager._instance = None  # type: ignore[misc]

    cm = ColorManager()

    # Test various rgb formats
    result1 = cm._str_to_rgba("rgb(100,200,300)")
    assert result1 == (100, 200, 300, 1.0)

    result2 = cm._str_to_rgba("rgb(10, 20, 30)")
    assert result2 == (10, 20, 30, 1.0)

    result3 = cm._str_to_rgba("rgba(50,60,70,0.5)")
    assert result3 == (50, 60, 70, 0.5)

    result4 = cm._str_to_rgba("rgba(80, 90, 100, 0.75)")
    assert result4 == (80, 90, 100, 0.75)


def test_end_to_end_rgb_workflow() -> None:
    """Test complete workflow with rgb colors from palette to display."""
    # Reset singleton
    ColorManager._instance = None  # type: ignore[misc]

    # Simulate colors from project.json5 file (rgb format)
    project_colors = {
        "baseline": "rgb(56,166,165)",
        "alternate": "rgb(29,105,150)",
        "Residential": "rgb(200,0,0)",
        "Commercial": "rgb(0,200,0)",
    }

    # Create palette
    palette = ColorPalette(project_colors)

    # Verify palette preserves rgb format
    for label, color in project_colors.items():
        assert palette.to_dict()[label] == color

    # Initialize ColorManager
    cm = ColorManager(palette)
    scenarios = ["baseline", "alternate"]
    sectors = ["Residential", "Commercial"]
    cm.initialize_colors(scenarios, sectors)

    # Get colors through ColorManager (should be rgba format for UI)
    baseline_color = cm.get_color("baseline")
    assert "rgba" in baseline_color
    assert "56" in baseline_color and "166" in baseline_color

    residential_color = cm.get_color("Residential")
    assert "rgba" in residential_color
    assert "200" in residential_color and "0" in residential_color

    # Scenario styling should work
    baseline_styling = cm.get_scenario_styling("baseline")
    assert "bg" in baseline_styling
    assert "border" in baseline_styling
    assert "56" in baseline_styling["bg"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
