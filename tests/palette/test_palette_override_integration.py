"""Integration test for palette override workflow."""

import json

import pytest

from stride.ui.palette import ColorPalette
from stride.ui.tui import (
    get_default_user_palette,
    load_user_palette,
    save_user_palette,
    set_default_user_palette,
)


@pytest.fixture
def test_env(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    """Set up isolated test environment."""
    config_dir = tmp_path / "stride_config"
    config_dir.mkdir()

    palette_dir = tmp_path / "palettes"
    palette_dir.mkdir()

    def mock_get_stride_config_dir():  # type: ignore[no-untyped-def]
        return config_dir

    def mock_get_user_palette_dir():  # type: ignore[no-untyped-def]
        return palette_dir

    monkeypatch.setattr("stride.ui.tui.get_stride_config_dir", mock_get_stride_config_dir)
    monkeypatch.setattr("stride.ui.tui.get_user_palette_dir", mock_get_user_palette_dir)

    return {
        "config_dir": config_dir,
        "palette_dir": palette_dir,
        "config_path": config_dir / "config.json",
        "palette_dir_path": palette_dir,
    }


def test_complete_workflow(test_env) -> None:  # type: ignore[no-untyped-def]
    """Test the complete palette override workflow."""
    # Step 1: Create a user palette
    residential_palette = {
        "Residential": "#E74C3C",
        "Commercial": "#3498DB",
        "Industrial": "#F39C12",
    }

    saved_path = save_user_palette("residential_colors", residential_palette)
    assert saved_path.exists()
    assert saved_path.parent == test_env["palette_dir"]

    # Step 2: Verify palette was saved correctly
    with open(saved_path) as f:
        data = json.load(f)
        assert data["palette"] == residential_palette

    # Step 3: Load the palette back
    loaded_palette = load_user_palette("residential_colors")
    assert isinstance(loaded_palette, ColorPalette)
    assert loaded_palette.to_dict() == residential_palette

    # Step 4: Verify no default is set initially
    assert get_default_user_palette() is None

    # Step 5: Set the palette as default
    set_default_user_palette("residential_colors")

    # Step 6: Verify default was set
    assert get_default_user_palette() == "residential_colors"

    # Step 7: Verify config file was created
    config_path = test_env["config_path"]
    assert config_path.exists()

    with open(config_path) as f:
        config = json.load(f)
        assert config["default_user_palette"] == "residential_colors"

    # Step 8: Create another palette
    commercial_palette = {
        "Office": "#2C3E50",
        "Retail": "#E74C3C",
        "Warehouse": "#95A5A6",
    }

    save_user_palette("commercial_colors", commercial_palette)

    # Step 9: Change the default
    set_default_user_palette("commercial_colors")
    assert get_default_user_palette() == "commercial_colors"

    # Step 10: Clear the default
    set_default_user_palette(None)
    assert get_default_user_palette() is None

    # Step 11: Verify config was updated
    with open(config_path) as f:
        config = json.load(f)
        assert "default_user_palette" not in config


def test_palette_override_simulation(test_env) -> None:  # type: ignore[no-untyped-def]
    """Simulate the dashboard startup palette selection logic."""
    # Create test palettes
    project_palette = {
        "Label1": "#FF0000",
        "Label2": "#00FF00",
    }

    user_palette_dict = {
        "Label1": "#0000FF",
        "Label2": "#FFFF00",
    }

    save_user_palette("custom", user_palette_dict)

    # Scenario 1: No default, no override -> use project palette
    selected_palette = project_palette
    palette_name = None

    if palette_name:
        selected_palette = load_user_palette(palette_name).to_dict()  # type: ignore[arg-type]
    elif get_default_user_palette():
        selected_palette = load_user_palette(get_default_user_palette()).to_dict()  # type: ignore[arg-type]

    assert selected_palette == project_palette

    # Scenario 2: Default set, no override -> use default
    set_default_user_palette("custom")
    selected_palette = project_palette
    palette_name = None

    if palette_name:
        selected_palette = load_user_palette(palette_name).to_dict()  # type: ignore[arg-type]
    elif get_default_user_palette():
        selected_palette = load_user_palette(get_default_user_palette()).to_dict()  # type: ignore[arg-type]

    assert selected_palette == user_palette_dict

    # Scenario 3: Default set, override specified -> use override
    other_palette_dict = {
        "Label1": "#AAAAAA",
        "Label2": "#BBBBBB",
    }
    save_user_palette("other", other_palette_dict)

    palette_name = "other"

    if palette_name:
        selected_palette = load_user_palette(palette_name).to_dict()  # type: ignore[arg-type]
    elif get_default_user_palette():
        selected_palette = load_user_palette(get_default_user_palette()).to_dict()  # type: ignore[arg-type]

    assert selected_palette == other_palette_dict

    # Scenario 4: Default set, --no-default-palette flag -> use project
    no_default_flag = True
    palette_name = None

    if palette_name:
        selected_palette = load_user_palette(palette_name).to_dict()  # type: ignore[arg-type]
    elif not no_default_flag and get_default_user_palette():
        selected_palette = load_user_palette(get_default_user_palette()).to_dict()  # type: ignore[arg-type]
    else:
        selected_palette = project_palette

    assert selected_palette == project_palette


def test_multiple_palettes(test_env) -> None:  # type: ignore[no-untyped-def]
    """Test managing multiple user palettes."""
    # Create multiple palettes
    palettes = {
        "corporate": {"Brand1": "#FF0000", "Brand2": "#00FF00"},
        "accessibility": {"High1": "#000000", "High2": "#FFFFFF"},
        "presentation": {"Slide1": "#2C3E50", "Slide2": "#E74C3C"},
    }

    for name, colors in palettes.items():
        save_user_palette(name, colors)

    # Verify all palettes exist
    palette_files = list(test_env["palette_dir"].glob("*.json"))
    assert len(palette_files) == 3

    # Test switching between defaults
    for name in palettes.keys():
        set_default_user_palette(name)
        assert get_default_user_palette() == name

    # Load each palette and verify
    for name, expected_colors in palettes.items():
        loaded = load_user_palette(name)
        assert loaded.to_dict() == expected_colors


def test_error_handling(test_env) -> None:  # type: ignore[no-untyped-def]
    """Test error handling for invalid operations."""
    # Try to load non-existent palette
    with pytest.raises(FileNotFoundError):
        load_user_palette("nonexistent")

    # Try to set non-existent palette as default
    with pytest.raises(FileNotFoundError):
        set_default_user_palette("nonexistent")

    # Create a palette and delete its file
    save_user_palette("temp", {"Label": "#FF0000"})
    set_default_user_palette("temp")

    # Delete the palette file
    palette_file = test_env["palette_dir"] / "temp.json"
    palette_file.unlink()

    # Now trying to load should fail
    with pytest.raises(FileNotFoundError):
        load_user_palette("temp")


def test_config_persistence_across_operations(test_env) -> None:  # type: ignore[no-untyped-def]
    """Test that config persists correctly across multiple operations."""
    # Perform various operations
    save_user_palette("p1", {"A": "#111111"})
    set_default_user_palette("p1")

    save_user_palette("p2", {"B": "#222222"})
    save_user_palette("p3", {"C": "#333333"})

    set_default_user_palette("p2")
    set_default_user_palette("p3")
    set_default_user_palette(None)

    save_user_palette("p4", {"D": "#444444"})
    set_default_user_palette("p4")

    # Final state should be p4 as default
    assert get_default_user_palette() == "p4"

    # Config file should exist and be valid
    config_path = test_env["config_path"]
    assert config_path.exists()

    with open(config_path) as f:
        config = json.load(f)
        assert config["default_user_palette"] == "p4"


def test_palette_content_integrity(test_env) -> None:  # type: ignore[no-untyped-def]
    """Test that palette content is preserved exactly."""
    # Test with various color formats and special characters
    complex_palette = {
        "Label with spaces": "#FF0000",
        "Label_with_underscores": "#00FF00",
        "Label-with-hyphens": "#0000FF",
        "Label.with.dots": "#FFFF00",
        "Label123": "#FF00FF",
        "123Label": "#00FFFF",
    }

    save_user_palette("complex", complex_palette)
    loaded = load_user_palette("complex")

    assert loaded.to_dict() == complex_palette

    # Verify each label individually
    for label, color in complex_palette.items():
        assert loaded.get(label) == color


def test_concurrent_palette_operations(test_env) -> None:  # type: ignore[no-untyped-def]
    """Test that multiple palette operations don't interfere."""
    # Create palettes
    for i in range(5):
        save_user_palette(f"palette{i}", {f"Label{i}": f"#{i:02d}0000"})

    # Set and change default multiple times
    for i in range(5):
        set_default_user_palette(f"palette{i}")
        assert get_default_user_palette() == f"palette{i}"

    # All palettes should still be loadable
    for i in range(5):
        loaded = load_user_palette(f"palette{i}")
        assert f"Label{i}" in loaded.to_dict()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
