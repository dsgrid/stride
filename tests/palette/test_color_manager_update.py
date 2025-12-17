"""Test that ColorManager properly updates when palette changes."""

import pytest

from stride.ui.color_manager import ColorManager
from stride.ui.palette import ColorPalette


def test_color_manager_updates_with_new_palette() -> None:
    """Test that ColorManager updates when a new palette is provided."""
    # Create first palette
    palette1 = ColorPalette({"Label1": "#FF0000", "Label2": "#00FF00"})
    cm1 = ColorManager(palette1)
    cm1.initialize_colors(["Label1", "Label2"])

    # Get colors from first palette
    color1_label1 = cm1.get_color("Label1")
    color1_label2 = cm1.get_color("Label2")

    # Verify colors are from first palette (red and green)
    assert "255, 0, 0" in color1_label1  # Red
    assert "0, 255, 0" in color1_label2  # Green

    # Create second palette with different colors
    palette2 = ColorPalette({"Label1": "#0000FF", "Label2": "#FFFF00"})
    cm2 = ColorManager(palette2)
    cm2.initialize_colors(["Label1", "Label2"])

    # Get colors from second palette
    color2_label1 = cm2.get_color("Label1")
    color2_label2 = cm2.get_color("Label2")

    # Verify colors are from second palette (blue and yellow)
    assert "0, 0, 255" in color2_label1  # Blue
    assert "255, 255, 0" in color2_label2  # Yellow

    # Verify they're the same instance (singleton)
    assert cm1 is cm2

    # Verify the instance now has the new colors
    assert "0, 0, 255" in cm1.get_color("Label1")
    assert "255, 255, 0" in cm1.get_color("Label2")


def test_color_manager_singleton_behavior() -> None:
    """Test that ColorManager maintains singleton behavior."""
    palette1 = ColorPalette({"A": "#111111"})
    cm1 = ColorManager(palette1)

    palette2 = ColorPalette({"A": "#222222"})
    cm2 = ColorManager(palette2)

    # Should be the same instance
    assert cm1 is cm2

    # Should have the updated palette
    color = cm2.get_color("A")
    assert "34, 34, 34" in color  # #222222 in RGB


def test_color_manager_initialization_without_palette() -> None:
    """Test that ColorManager can be initialized without a palette."""
    # Reset singleton for clean test
    ColorManager._instance = None  # type: ignore[misc]

    cm = ColorManager()
    cm.initialize_colors(["Label1", "Label2"])

    # Should auto-generate colors
    color1 = cm.get_color("Label1")
    color2 = cm.get_color("Label2")

    assert color1 is not None
    assert color2 is not None
    assert "rgba" in color1
    assert "rgba" in color2


def test_color_manager_reinitialize_colors() -> None:
    """Test that colors can be reinitialized with a new palette."""
    # Reset singleton
    ColorManager._instance = None  # type: ignore[misc]

    # First initialization
    palette1 = ColorPalette(
        {
            "Residential": "#E74C3C",
            "Commercial": "#3498DB",
            "Industrial": "#F39C12",
        }
    )
    cm = ColorManager(palette1)
    cm.initialize_colors(["Residential", "Commercial", "Industrial"])

    # Store first colors
    res1 = cm.get_color("Residential")
    com1 = cm.get_color("Commercial")
    ind1 = cm.get_color("Industrial")

    # Update with new palette
    palette2 = ColorPalette(
        {
            "Residential": "#2C3E50",
            "Commercial": "#E74C3C",
            "Industrial": "#ECF0F1",
        }
    )
    cm2 = ColorManager(palette2)
    cm2.initialize_colors(["Residential", "Commercial", "Industrial"])

    # Get new colors
    res2 = cm2.get_color("Residential")
    com2 = cm2.get_color("Commercial")
    ind2 = cm2.get_color("Industrial")

    # Colors should be different
    assert res1 != res2
    assert com1 != com2
    assert ind1 != ind2

    # New colors should match new palette
    assert "44, 62, 80" in res2  # #2C3E50
    assert "231, 76, 60" in com2  # #E74C3C
    assert "236, 240, 241" in ind2  # #ECF0F1


def test_color_manager_scenario_styling_updates() -> None:
    """Test that scenario styling updates with new palette."""
    # Reset singleton
    ColorManager._instance = None  # type: ignore[misc]

    palette1 = ColorPalette({"Scenario1": "#FF0000"})
    cm1 = ColorManager(palette1)
    cm1.initialize_colors(["Scenario1"])

    styling1 = cm1.get_scenario_styling("Scenario1")
    assert "255, 0, 0" in styling1["bg"]
    assert "255, 0, 0" in styling1["border"]

    # Update palette
    palette2 = ColorPalette({"Scenario1": "#0000FF"})
    cm2 = ColorManager(palette2)
    cm2.initialize_colors(["Scenario1"])

    styling2 = cm2.get_scenario_styling("Scenario1")
    assert "0, 0, 255" in styling2["bg"]
    assert "0, 0, 255" in styling2["border"]

    # Styling should have changed
    assert styling1["bg"] != styling2["bg"]
    assert styling1["border"] != styling2["border"]


def test_color_manager_preserves_palette_reference() -> None:
    """Test that ColorManager properly references the provided palette."""
    palette = ColorPalette({"Label": "#123456"})
    cm = ColorManager(palette)

    # Get the palette back
    retrieved_palette = cm.get_palette()

    # Should be the same palette instance
    assert retrieved_palette is palette

    # Update palette directly
    palette.update("NewLabel", "#ABCDEF")

    # ColorManager should see the change
    color = cm.get_color("NewLabel")
    assert "171, 205, 239" in color  # #ABCDEF


def test_color_manager_multiple_scenarios() -> None:
    """Test ColorManager with multiple scenarios across palette updates."""
    # Reset singleton
    ColorManager._instance = None  # type: ignore[misc]

    scenarios = ["Scenario1", "Scenario2", "Scenario3"]
    sectors = ["Residential", "Commercial", "Industrial"]

    # First palette
    palette1 = ColorPalette(
        {
            "Scenario1": "#FF0000",
            "Scenario2": "#00FF00",
            "Scenario3": "#0000FF",
            "Residential": "#FFFF00",
            "Commercial": "#FF00FF",
            "Industrial": "#00FFFF",
        }
    )

    cm1 = ColorManager(palette1)
    cm1.initialize_colors(scenarios, sectors)

    # Get all styling
    all_styling1 = cm1.get_all_scenario_styling()
    assert len(all_styling1) == 3

    # Update palette with completely different colors
    palette2 = ColorPalette(
        {
            "Scenario1": "#111111",
            "Scenario2": "#222222",
            "Scenario3": "#333333",
            "Residential": "#444444",
            "Commercial": "#555555",
            "Industrial": "#666666",
        }
    )

    cm2 = ColorManager(palette2)
    cm2.initialize_colors(scenarios, sectors)

    # Get all styling again
    all_styling2 = cm2.get_all_scenario_styling()
    assert len(all_styling2) == 3

    # All styling should be different
    for scenario in scenarios:
        assert all_styling1[scenario]["bg"] != all_styling2[scenario]["bg"]
        assert all_styling1[scenario]["border"] != all_styling2[scenario]["border"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
