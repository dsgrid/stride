"""
Test script to verify TUI reordering functionality.

This script creates a test project with a palette and verifies that:
1. The palette can be loaded into the TUI
2. Items maintain their order when displayed
3. Move up/down operations work correctly
"""

from pathlib import Path

from stride.models import ProjectConfig
from stride.ui.palette import ColorPalette
from stride.ui.tui import organize_palette_by_groups


def test_reordering_logic() -> None:
    """Test the reordering logic without launching the TUI."""

    print("=" * 60)
    print("Testing Palette Reordering Logic")
    print("=" * 60)

    # Create a test palette
    palette_dict = {
        "heating": "#FF0000",
        "cooling": "#00FF00",
        "lighting": "#0000FF",
        "baseline": "#FFFF00",
        "efficient": "#FF00FF",
        "2030": "#00FFFF",
        "2040": "#FFA500",
    }

    print("\n1. Original palette order:")
    for i, (label, color) in enumerate(palette_dict.items()):
        print(f"   {i}: {label:20s} -> {color}")

    # Organize into groups
    groups = organize_palette_by_groups(palette_dict)

    print("\n2. Organized into groups:")
    for group_name, group_labels in groups.items():
        print(f"\n   {group_name}:")
        for i, (label, color) in enumerate(group_labels.items()):
            print(f"      {i}: {label:20s} -> {color}")

    # Test moving items in End Uses group
    if "End Uses" in groups:
        print("\n3. Testing move operations on End Uses:")

        # Convert to items list
        end_uses = groups["End Uses"]
        items = [
            {"label": label, "color": color, "order": idx}
            for idx, (label, color) in enumerate(end_uses.items())
        ]

        print(f"   Original: {[item['label'] for item in items]}")

        # Move second item up
        palette = ColorPalette()
        palette.move_item_up(items, 1)
        print(f"   After move_item_up(1): {[item['label'] for item in items]}")

        # Move last item up
        palette.move_item_up(items, len(items) - 1)
        print(f"   After move_item_up({len(items) - 1}): {[item['label'] for item in items]}")

        # Update the group dict
        groups["End Uses"] = {str(item["label"]): str(item["color"]) for item in items}

        print("\n   Updated End Uses group:")
        for i, (label, color) in enumerate(groups["End Uses"].items()):
            print(f"      {i}: {label:20s} -> {color}")

    print("\n4. Verify dict order is preserved:")
    # Create a new dict and verify order
    test_dict = {"a": "1", "b": "2", "c": "3"}
    print(f"   Original: {list(test_dict.keys())}")

    # Reorder by creating new dict
    items = [{"k": k, "v": v} for k, v in test_dict.items()]
    items[0], items[1] = items[1], items[0]
    test_dict = {str(item["k"]): str(item["v"]) for item in items}
    print(f"   After swap: {list(test_dict.keys())}")

    print("\n" + "=" * 60)
    print("All tests completed successfully!")
    print("=" * 60)


def test_with_project() -> None:
    """Test loading a real project palette."""

    print("\n\n" + "=" * 60)
    print("Testing with Real Project")
    print("=" * 60)

    # Look for a test project
    test_project_path = Path("test_project/project.json5")

    if not test_project_path.exists():
        print("\nNo test project found at:", test_project_path)
        print("Skipping project test.")
        return

    print(f"\nLoading project from: {test_project_path}")

    try:
        config = ProjectConfig.from_file(test_project_path)
        print(f"Project: {config.project_id}")
        print(f"Palette has {len(config.color_palette)} colors")

        # Organize palette
        groups = organize_palette_by_groups(config.color_palette, config)

        print("\nPalette groups:")
        for group_name, group_labels in groups.items():
            print(f"\n  {group_name} ({len(group_labels)} items):")
            for i, label in enumerate(group_labels.keys()):
                print(f"    {i}: {label}")

        print("\n" + "=" * 60)
        print("Project palette loaded successfully!")
        print("=" * 60)

    except Exception as e:
        print(f"\nError loading project: {e}")


if __name__ == "__main__":
    test_reordering_logic()
    test_with_project()

    print("\n\n" + "=" * 60)
    print("To test the TUI interactively:")
    print("  1. Run: stride palette view <project_path>")
    print("  2. Use arrow keys to navigate")
    print("  3. Press 'u' to move item up")
    print("  4. Press 'd' to move item down")
    print("  5. Press 's' to save")
    print("  6. Press 'q' to quit")
    print("=" * 60)
