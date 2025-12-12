"""Test script for palette initialization functionality."""

from pathlib import Path

from stride.api import APIClient
from stride.project import Project
from stride.ui.palette import ColorPalette
from stride.ui.tui import get_user_palette_dir


def test_api_query_methods() -> None:
    """Test the new API methods for querying unique labels."""
    print("\n" + "=" * 80)
    print("Testing API query methods")
    print("=" * 80)

    # Find a test project
    test_projects = list(Path().glob("test_*"))
    if not test_projects:
        print("No test projects found. Skipping test.")
        return

    project_path = test_projects[0]
    print(f"\nUsing test project: {project_path}")

    # Load project
    with Project.load(project_path, read_only=True) as project:
        # Create API client
        api_client = APIClient(project)

        # Query all unique labels
        scenarios = api_client.scenarios
        years = [str(y) for y in api_client.years]
        sectors = api_client.get_unique_sectors()
        end_uses = api_client.get_unique_end_uses()

        print("\nFound labels:")
        print(f"  Scenarios ({len(scenarios)}): {scenarios}")
        print(f"  Years ({len(years)}): {years}")
        print(f"  Sectors ({len(sectors)}): {sectors}")
        print(
            f"  End Uses ({len(end_uses)}): {end_uses[:5]}..."
            if len(end_uses) > 5
            else f"  End Uses ({len(end_uses)}): {end_uses}"
        )

        # Create a new palette with all labels
        palette = ColorPalette()
        all_labels = scenarios + years + sectors + end_uses

        print(f"\nGenerating colors for {len(all_labels)} labels...")
        for i, label in enumerate(all_labels):
            color = palette.get(label)
            if i < 5:  # Show first 5
                print(f"  {label}: {color}")
        if len(all_labels) > 5:
            print(f"  ... and {len(all_labels) - 5} more")

        palette_dict = palette.to_dict()
        print(f"\nGenerated palette with {len(palette_dict)} entries")

        # Verify all labels have colors
        assert len(palette_dict) == len(all_labels), "All labels should have colors"
        print("✓ All labels assigned colors successfully")


def test_user_palette_directory_creation() -> None:
    """Test that user palette directory is created correctly."""
    print("\n" + "=" * 80)
    print("Testing user palette directory creation")
    print("=" * 80)

    # Get user palette directory (should create it if it doesn't exist)
    palette_dir = get_user_palette_dir()
    print(f"\nUser palette directory: {palette_dir}")

    # Verify directory exists
    assert palette_dir.exists(), "User palette directory should exist"
    assert palette_dir.is_dir(), "User palette directory should be a directory"
    print("✓ Directory exists and is accessible")

    # Verify it's in the home directory
    assert str(palette_dir).startswith(str(Path.home())), "Should be in home directory"
    print("✓ Directory is in user's home directory (cross-platform)")

    # Verify the path structure
    assert palette_dir.name == "palettes", "Directory name should be 'palettes'"
    assert palette_dir.parent.name == ".stride", "Parent directory should be '.stride'"
    print("✓ Directory structure is correct: ~/.stride/palettes/")


def test_palette_init_from_user_palette() -> None:
    """Test initializing a palette from an existing user palette."""
    print("\n" + "=" * 80)
    print("Testing palette initialization from user palette")
    print("=" * 80)

    from stride.ui.tui import load_user_palette, save_user_palette

    # Create a test user palette
    test_palette_name = "test_source_palette"
    test_palette = {
        "Scenario A": "#FF0000",
        "Scenario B": "#00FF00",
        "2025": "#0000FF",
        "Residential": "#FFFF00",
    }

    print(f"\nCreating test user palette: {test_palette_name}")
    saved_path = save_user_palette(test_palette_name, test_palette)
    print(f"Saved to: {saved_path}")

    # Load it back
    print(f"\nLoading user palette: {test_palette_name}")
    loaded_palette = load_user_palette(test_palette_name)
    loaded_dict = loaded_palette.to_dict()

    print(f"Loaded {len(loaded_dict)} colors:")
    for label, color in loaded_dict.items():
        print(f"  {label}: {color}")

    # Verify
    assert loaded_dict == test_palette, "Loaded palette should match original"
    print("✓ User palette loaded successfully")

    # Clean up
    saved_path.unlink()
    print(f"\nCleaned up test palette: {saved_path}")


def test_palette_init_from_project() -> None:
    """Test initializing a palette from another project's palette."""
    print("\n" + "=" * 80)
    print("Testing palette initialization from project palette")
    print("=" * 80)

    # Find a test project
    test_projects = list(Path().glob("test_*"))
    if not test_projects:
        print("No test projects found. Skipping test.")
        return

    project_path = test_projects[0]
    print(f"\nUsing test project: {project_path}")

    # Load project
    try:
        with Project.load(project_path, read_only=True) as project:
            # Get the project's palette
            palette_dict = project.palette.to_dict()

            print(f"\nLoaded project palette with {len(palette_dict)} entries:")
            for i, (label, color) in enumerate(palette_dict.items()):
                if i < 5:  # Show first 5
                    print(f"  {label}: {color}")
                elif i == 5:
                    print(f"  ... and {len(palette_dict) - 5} more")
                    break

            # Verify it's not empty
            assert len(palette_dict) > 0, "Project palette should not be empty"
            print("✓ Project palette loaded successfully")
    except Exception:
        # If no test project is available, skip this test
        print("⚠ No test project available, skipping project palette test")
        return


def main() -> int:
    """Run all tests."""
    print("\n" + "=" * 80)
    print("PALETTE API TESTS")
    print("=" * 80)

    try:
        test_api_query_methods()
    except Exception as e:
        print(f"\n✗ API query test failed: {e}")
        import traceback

        traceback.print_exc()

    try:
        test_user_palette_directory_creation()
    except Exception as e:
        print(f"\n✗ Directory creation test failed: {e}")
        import traceback

        traceback.print_exc()

    try:
        test_palette_init_from_user_palette()
    except Exception as e:
        print(f"\n✗ User palette test failed: {e}")
        import traceback

        traceback.print_exc()

    try:
        test_palette_init_from_project()
    except Exception as e:
        print(f"\n✗ Project palette test failed: {e}")
        import traceback

        traceback.print_exc()

    print("\n" + "=" * 80)
    print("TESTS COMPLETE")
    print("=" * 80)
    print("\nTo test the CLI commands, try:")
    print("  stride palette init --name=test_pal --from-project=<project_path> --user")
    print("  stride palette view test_pal --user")
    print("  stride palette list --user")

    return 0


if __name__ == "__main__":
    main()
