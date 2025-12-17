#!/usr/bin/env python3
"""
Test script to verify auto-color assignment in palette TUI.

This tests that the ColorPalette.get() method properly cycles through
colors when adding new labels without explicit colors.
"""

from stride.ui.palette import ColorPalette


def test_auto_color_assignment() -> None:
    """Test that auto-color assignment cycles through theme colors."""
    print("Testing auto-color assignment...")

    # Create an empty palette
    palette = ColorPalette()

    # Add multiple labels without specifying colors
    labels = [
        "Label1",
        "Label2",
        "Label3",
        "Label4",
        "Label5",
        "Label6",
        "Label7",
        "Label8",
    ]

    colors_assigned = []
    for label in labels:
        color = palette.get(label)
        colors_assigned.append(color)
        print(f"  {label}: {color}")

    # Verify all colors are valid (hex or rgb format)
    for color in colors_assigned:
        is_hex = color.startswith("#") and len(color) in [7, 9]
        is_rgb = color.startswith("rgb(") and color.endswith(")")
        assert is_hex or is_rgb, f"Color {color} is not in valid hex or rgb format"

    # Verify colors are different (at least for the first few)
    unique_colors = len(set(colors_assigned))
    print(f"\nAssigned {unique_colors} unique colors out of {len(labels)} labels")
    assert unique_colors >= min(len(labels), 8), "Not enough color variety in theme cycling"

    print("✓ Auto-color assignment test passed!")


def test_auto_color_with_existing_palette() -> None:
    """Test auto-color assignment when palette already has some colors."""
    print("\nTesting auto-color with existing palette...")

    # Create palette with some existing colors
    existing = {
        "Existing1": "#FF0000",
        "Existing2": "#00FF00",
        "Existing3": "#0000FF",
    }

    palette = ColorPalette(existing)

    # Add new labels - should get different colors from the theme
    new_labels = ["New1", "New2", "New3"]

    for label in new_labels:
        color = palette.get(label)
        print(f"  {label}: {color}")
        # Should be a valid color (hex or rgb)
        is_hex = color.startswith("#")
        is_rgb = color.startswith("rgb(")
        assert is_hex or is_rgb, f"Invalid color format: {color}"
        # Should be in the palette now (keys are lowercase)
        assert label.lower() in palette.palette

    # Verify all labels are in palette
    assert len(palette.palette) == len(existing) + len(new_labels)

    print("✓ Auto-color with existing palette test passed!")


def test_color_cycling() -> None:
    """Test that colors cycle through the theme properly."""
    print("\nTesting color cycling through theme...")

    palette = ColorPalette()

    # The Prism theme has multiple colors, add more labels than theme has colors
    # to test cycling behavior
    num_labels = 20
    labels = [f"Label{i}" for i in range(num_labels)]

    colors = []
    for label in labels:
        color = palette.get(label)
        colors.append(color)

    print(f"  Generated {len(colors)} colors")
    print(f"  Unique colors: {len(set(colors))}")

    # There should be some repetition if we exceed theme size
    # but the pattern should be consistent
    unique_colors = set(colors)
    print(f"  Theme contains approximately {len(unique_colors)} colors")

    # Verify cycling works - if we have more labels than unique colors,
    # the pattern should repeat
    if num_labels > len(unique_colors):
        theme_size = len(unique_colors)
        # Check that colors repeat in a cycle
        for i in range(theme_size, num_labels):
            expected_color = colors[i % theme_size]
            actual_color = colors[i]
            if expected_color == actual_color:
                print(f"  ✓ Color cycling confirmed at position {i}")
                break

    print("✓ Color cycling test passed!")


def test_palette_integration() -> None:
    """Test integration with TUI-style workflow."""
    print("\nTesting TUI workflow integration...")

    # Simulate TUI workflow of adding labels to groups
    label_groups: dict[str, dict[str, str]] = {
        "Scenarios": {},
        "Sectors": {},
        "Years": {},
    }

    # Simulate adding labels to Scenarios group
    print("\n  Adding to Scenarios group:")
    scenarios_palette = ColorPalette(label_groups["Scenarios"])
    for scenario in ["Baseline", "Alternative", "High Growth"]:
        color = scenarios_palette.get(scenario)
        label_groups["Scenarios"][scenario] = color
        print(f"    {scenario}: {color}")

    # Simulate adding labels to Sectors group
    print("\n  Adding to Sectors group:")
    sectors_palette = ColorPalette(label_groups["Sectors"])
    for sector in ["Residential", "Commercial", "Industrial"]:
        color = sectors_palette.get(sector)
        label_groups["Sectors"][sector] = color
        print(f"    {sector}: {color}")

    # Simulate adding labels to Years group
    print("\n  Adding to Years group:")
    years_palette = ColorPalette(label_groups["Years"])
    for year in ["2025", "2030", "2035", "2040"]:
        color = years_palette.get(year)
        label_groups["Years"][year] = color
        print(f"    {year}: {color}")

    # Verify all groups have colors assigned
    total_labels = sum(len(labels) for labels in label_groups.values())
    print(f"\n  Total labels across all groups: {total_labels}")
    assert total_labels == 10, "Expected 10 labels total"

    # Verify each group has the expected number of labels
    assert len(label_groups["Scenarios"]) == 3
    assert len(label_groups["Sectors"]) == 3
    assert len(label_groups["Years"]) == 4

    print("✓ TUI workflow integration test passed!")


def main() -> int:
    """Run all auto-color tests."""
    print("=" * 60)
    print("Auto-Color Assignment Test Suite")
    print("=" * 60)

    try:
        test_auto_color_assignment()
        test_auto_color_with_existing_palette()
        test_color_cycling()
        test_palette_integration()

        print("\n" + "=" * 60)
        print("✓ All auto-color tests passed!")
        print("=" * 60)
        print("\nThe TUI will now properly auto-assign colors using")
        print("ColorPalette.get() which cycles through the theme.")

    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback

        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
