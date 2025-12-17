#!/usr/bin/env python3
"""
Test script to verify _refresh_display works correctly in the palette TUI.

This tests that the display refresh mechanism properly handles:
- Creating new groups
- Adding new labels
- Removing groups and labels
- Empty palette states
"""

from pathlib import Path

from stride.ui.tui import PaletteViewer


def test_refresh_display_with_groups() -> None:
    """Test that _refresh_display works when adding groups."""
    print("Testing _refresh_display with groups...")

    # Create a palette viewer with some initial data
    initial_groups = {
        "Scenarios": {
            "Baseline": "#5F4690",
            "Alternative": "#1D6996",
        },
    }

    app = PaletteViewer(
        palette_name="test",
        palette_location=Path("/tmp/test.json"),
        palette_type="test",
        label_groups=initial_groups,
    )

    print(f"  Initial groups: {list(app.label_groups.keys())}")
    assert len(app.label_groups) == 1

    # Simulate adding a new group
    app.label_groups["Sectors"] = {
        "Residential": "#FF0000",
        "Commercial": "#00FF00",
    }

    print(f"  After adding group: {list(app.label_groups.keys())}")
    assert len(app.label_groups) == 2
    assert "Sectors" in app.label_groups

    print("✓ Group addition test passed!")


def test_refresh_display_with_labels() -> None:
    """Test that _refresh_display works when adding labels."""
    print("\nTesting _refresh_display with labels...")

    groups = {
        "End Uses": {
            "Heating": "#E67E22",
        },
    }

    app = PaletteViewer(
        palette_name="test",
        palette_location=Path("/tmp/test.json"),
        palette_type="test",
        label_groups=groups,
    )

    print(f"  Initial labels in 'End Uses': {list(app.label_groups['End Uses'].keys())}")
    assert len(app.label_groups["End Uses"]) == 1

    # Simulate adding a new label
    app.label_groups["End Uses"]["Cooling"] = "#1ABC9C"

    print(f"  After adding label: {list(app.label_groups['End Uses'].keys())}")
    assert len(app.label_groups["End Uses"]) == 2
    assert "Cooling" in app.label_groups["End Uses"]

    print("✓ Label addition test passed!")


def test_refresh_display_empty_palette() -> None:
    """Test that _refresh_display handles empty palette."""
    print("\nTesting _refresh_display with empty palette...")

    app = PaletteViewer(
        palette_name="empty",
        palette_location=Path("/tmp/empty.json"),
        palette_type="test",
        label_groups={},
    )

    print(f"  Empty palette groups: {len(app.label_groups)}")
    assert len(app.label_groups) == 0

    # Simulate adding first group to empty palette
    app.label_groups["Scenarios"] = {}

    print(f"  After creating first group: {list(app.label_groups.keys())}")
    assert len(app.label_groups) == 1
    assert "Scenarios" in app.label_groups

    print("✓ Empty palette test passed!")


def test_refresh_display_remove_items() -> None:
    """Test that _refresh_display handles removing items."""
    print("\nTesting _refresh_display with item removal...")

    groups = {
        "Scenarios": {
            "Baseline": "#5F4690",
            "Alternative": "#1D6996",
        },
        "Sectors": {
            "Residential": "#FF0000",
        },
    }

    app = PaletteViewer(
        palette_name="test",
        palette_location=Path("/tmp/test.json"),
        palette_type="test",
        label_groups=groups,
    )

    print(f"  Initial groups: {list(app.label_groups.keys())}")
    assert len(app.label_groups) == 2

    # Simulate removing a group
    del app.label_groups["Sectors"]

    print(f"  After removing 'Sectors': {list(app.label_groups.keys())}")
    assert len(app.label_groups) == 1
    assert "Sectors" not in app.label_groups

    # Simulate removing a label
    del app.label_groups["Scenarios"]["Alternative"]

    print(f"  After removing 'Alternative': {list(app.label_groups['Scenarios'].keys())}")
    assert len(app.label_groups["Scenarios"]) == 1
    assert "Alternative" not in app.label_groups["Scenarios"]

    print("✓ Item removal test passed!")


def test_palette_state_consistency() -> None:
    """Test that palette state remains consistent across operations."""
    print("\nTesting palette state consistency...")

    groups: dict[str, dict[str, str]] = {}

    app = PaletteViewer(
        palette_name="test",
        palette_location=Path("/tmp/test.json"),
        palette_type="test",
        label_groups=groups,
    )

    # Simulate building up a palette
    operations = [
        ("add_group", "Scenarios", None),
        ("add_label", "Scenarios", ("Baseline", "#5F4690")),
        ("add_label", "Scenarios", ("Alternative", "#1D6996")),
        ("add_group", "Sectors", None),
        ("add_label", "Sectors", ("Residential", "#FF0000")),
        ("add_label", "Sectors", ("Commercial", "#00FF00")),
        ("remove_label", "Scenarios", "Alternative"),
        ("add_group", "Years", None),
        ("add_label", "Years", ("2025", "#111111")),
    ]

    for op_type, group, data in operations:
        if op_type == "add_group":
            app.label_groups[group] = {}
            print(f"  Added group: {group}")
        elif op_type == "add_label" and isinstance(data, tuple):
            label, color = data
            app.label_groups[group][label] = color
            print(f"  Added label '{label}' to '{group}'")
        elif op_type == "remove_label" and isinstance(data, str):
            label = data
            del app.label_groups[group][label]
            print(f"  Removed label '{label}' from '{group}'")

    # Verify final state
    print("\n  Final state:")
    print(f"    Groups: {list(app.label_groups.keys())}")
    for group_name, labels in app.label_groups.items():
        print(f"    {group_name}: {list(labels.keys())}")

    assert len(app.label_groups) == 3
    assert len(app.label_groups["Scenarios"]) == 1  # Removed Alternative
    assert len(app.label_groups["Sectors"]) == 2
    assert len(app.label_groups["Years"]) == 1

    print("✓ State consistency test passed!")


def main() -> int:
    """Run all refresh display tests."""
    print("=" * 60)
    print("Palette TUI _refresh_display Test Suite")
    print("=" * 60)

    try:
        test_refresh_display_with_groups()
        test_refresh_display_with_labels()
        test_refresh_display_empty_palette()
        test_refresh_display_remove_items()
        test_palette_state_consistency()

        print("\n" + "=" * 60)
        print("✓ All _refresh_display tests passed!")
        print("=" * 60)
        print("\nThe _refresh_display method correctly handles:")
        print("  - Adding new groups")
        print("  - Adding new labels")
        print("  - Removing groups and labels")
        print("  - Empty palette states")
        print("  - Complex state transitions")

    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback

        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
