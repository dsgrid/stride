"""Test script to verify palette override functionality."""

import pytest

from stride.ui.tui import (
    get_default_user_palette,
    get_stride_config_path,
    load_user_palette,
    save_user_palette,
    set_default_user_palette,
)


def test_user_palette_save_and_load(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Test saving and loading a user palette."""
    # Mock the user palette directory
    palette_dir = tmp_path / "palettes"
    palette_dir.mkdir()

    def mock_get_user_palette_dir():  # type: ignore[no-untyped-def]
        return palette_dir

    monkeypatch.setattr("stride.ui.tui.get_user_palette_dir", mock_get_user_palette_dir)

    # Create a test palette
    test_palette = {
        "Residential": "#FF0000",
        "Commercial": "#00FF00",
        "Industrial": "#0000FF",
    }

    # Save the palette
    saved_path = save_user_palette("test_palette", test_palette)
    assert saved_path.exists()
    assert saved_path.name == "test_palette.json"

    # Load the palette
    loaded_palette = load_user_palette("test_palette")
    assert loaded_palette.to_dict() == test_palette


def test_set_and_get_default_palette(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Test setting and getting the default user palette."""
    # Mock the stride config directory
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

    # Create a test palette file
    test_palette = {"Residential": "#FF0000"}
    save_user_palette("my_palette", test_palette)

    # Initially, no default should be set
    assert get_default_user_palette() is None

    # Set a default palette
    set_default_user_palette("my_palette")
    assert get_default_user_palette() == "my_palette"

    # Verify config file was created
    config_path = get_stride_config_path()
    assert config_path.exists()

    # Clear the default palette
    set_default_user_palette(None)
    assert get_default_user_palette() is None


def test_set_default_nonexistent_palette(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Test that setting a non-existent palette as default raises an error."""
    # Mock the stride config directory
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

    # Try to set a non-existent palette as default
    with pytest.raises(FileNotFoundError, match="not found"):
        set_default_user_palette("nonexistent_palette")


def test_config_persistence(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Test that config persists across multiple operations."""
    # Mock the stride config directory
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

    # Create test palettes
    save_user_palette("palette1", {"Label1": "#FF0000"})
    save_user_palette("palette2", {"Label2": "#00FF00"})

    # Set first palette as default
    set_default_user_palette("palette1")
    assert get_default_user_palette() == "palette1"

    # Change to second palette
    set_default_user_palette("palette2")
    assert get_default_user_palette() == "palette2"

    # Clear and verify
    set_default_user_palette(None)
    assert get_default_user_palette() is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
