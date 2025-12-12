#!/usr/bin/env python3
"""
Test script to verify the palette TUI can be instantiated and basic functions work.

This script tests the palette TUI without actually launching it (which would require a TTY).
"""

from pathlib import Path

from stride.models import ProjectConfig
from stride.ui.tui import (
    get_user_palette_dir,
    list_user_palettes,
    organize_palette_by_groups,
    save_user_palette,
)


def test_organize_palette() -> None:
    """Test palette organization into groups."""
    print("Testing palette organization...")

    # Sample palette with various label types
    test_palette = {
        "residential": "#5F4690",
        "commercial": "#FF5733",
        "industrial": "#3498DB",
        "transportation": "#E74C3C",
        "baseline": "rgb(115, 175, 72)",
        "alternate_gdp": "rgb(56, 166, 165)",
        "2025": "rgb(237, 173, 8)",
        "2030": "rgb(204, 80, 62)",
        "2035": "rgb(111, 64, 112)",
        "cooling": "#1ABC9C",
        "heating": "#E67E22",
        "lighting": "#9B59B6",
        "water_heating": "#16A085",
        "other_label": "#95A5A6",
    }

    # Organize the palette
    groups = organize_palette_by_groups(test_palette)

    print(f"\nOrganized into {len(groups)} groups:")
    for group_name, labels in groups.items():
        print(f"  {group_name}: {len(labels)} labels")
        for label in sorted(labels.keys()):
            print(f"    - {label}: {labels[label]}")

    # Verify expected groups exist
    assert "Scenarios" in groups
    assert "Model Years" in groups
    assert "Metrics" in groups

    # Verify correct categorization (everything goes to Metrics for flat palette)
    assert "residential" in groups["Metrics"]
    assert "2025" in groups["Metrics"]
    assert "baseline" in groups["Metrics"]
    assert "cooling" in groups["Metrics"]
    # In legacy flat format, everything is categorized as Metrics
    assert len(groups["Scenarios"]) == 0
    assert len(groups["Model Years"]) == 0
    assert len(groups["Metrics"]) == len(test_palette)

    print("\n✓ Palette organization test passed!")


def test_user_palette_operations() -> None:
    """Test user palette save/load operations."""
    print("\nTesting user palette operations...")

    # Get user palette directory
    palette_dir = get_user_palette_dir()
    print(f"User palette directory: {palette_dir}")
    assert palette_dir.exists()

    # Create a test palette
    test_palette = {
        "label1": "#FF0000",
        "label2": "#00FF00",
        "label3": "#0000FF",
    }

    # Save the palette
    test_name = "test_palette"
    saved_path = save_user_palette(test_name, test_palette)
    print(f"Saved test palette to: {saved_path}")
    assert saved_path.exists()

    # List palettes
    palettes = list_user_palettes()
    print(f"Found {len(palettes)} user palette(s)")

    # Clean up test palette
    saved_path.unlink()
    print("Cleaned up test palette")

    print("✓ User palette operations test passed!")


def test_project_palette_loading() -> None:
    """Test loading palette from a project."""
    print("\nTesting project palette loading...")

    # Path to test project
    project_path = Path("test_project/project.json5")

    if not project_path.exists():
        print(f"Warning: Test project not found at {project_path}")
        print("Skipping project palette test")
        return

    # Load project config
    config = ProjectConfig.from_file(project_path)
    print(f"Loaded project: {config.project_id}")

    # Check palette
    palette = config.color_palette
    print(f"Project palette has {len(palette)} colors")

    # Organize into groups
    groups = organize_palette_by_groups(palette, config)
    print(f"\nOrganized into {len(groups)} groups:")
    for group_name, labels in groups.items():
        print(f"  {group_name}: {len(labels)} labels")

    print("✓ Project palette loading test passed!")


def test_palette_viewer_instantiation() -> None:
    """Test that PaletteViewer can be instantiated."""
    print("\nTesting PaletteViewer instantiation...")

    from stride.ui.tui import PaletteViewer

    # Create test data
    test_groups = {
        "End Uses": {
            "cooling": "#1ABC9C",
            "heating": "#E67E22",
        },
        "Scenarios": {
            "baseline": "#73AF48",
            "alternate": "#38A6A5",
        },
    }

    # Instantiate the viewer (but don't run it)
    app = PaletteViewer(
        palette_name="test_palette",
        palette_location=Path("/tmp/test.json"),
        palette_type="test",
        label_groups=test_groups,
    )

    print(f"Created PaletteViewer instance: {app.__class__.__name__}")
    print(f"  Palette name: {app.palette_name}")
    print(f"  Palette type: {app.palette_type}")
    print(f"  Label groups: {len(app.label_groups)}")

    print("✓ PaletteViewer instantiation test passed!")


def main() -> int:
    """Run all tests."""
    print("=" * 60)
    print("Palette TUI Test Suite")
    print("=" * 60)

    try:
        test_organize_palette()
        test_user_palette_operations()
        test_project_palette_loading()
        test_palette_viewer_instantiation()

        print("\n" + "=" * 60)
        print("✓ All tests passed!")
        print("=" * 60)

    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback

        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
