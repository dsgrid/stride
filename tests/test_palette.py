"""Tests for the ColorPalette class."""

import pytest

from stride.ui.palette import ColorPalette


class TestColorPaletteInitialization:
    """Test ColorPalette initialization."""

    def test_empty_initialization(self) -> None:
        """Test creating an empty palette."""
        palette = ColorPalette()
        assert isinstance(palette.palette, dict)
        assert len(palette.palette) == 0

    def test_initialization_with_dict(self) -> None:
        """Test creating a palette with initial colors."""
        initial_colors = {
            "residential": "#FF5733",
            "commercial": "#3498DB",
        }
        palette = ColorPalette(palette=initial_colors)
        assert len(palette.palette) == 2
        assert palette.palette["residential"] == "#FF5733"
        assert palette.palette["commercial"] == "#3498DB"

    def test_initialization_with_invalid_colors(self) -> None:
        """Test that invalid colors are replaced during initialization."""
        initial_colors = {
            "residential": "not_a_color",
            "commercial": "#3498DB",
        }
        palette = ColorPalette(palette=initial_colors)
        assert len(palette.palette) == 2
        assert palette.palette["commercial"] == "#3498DB"
        # Invalid color should be replaced with a generated one
        assert palette.palette["residential"] != "not_a_color"


class TestColorPaletteUpdate:
    """Test ColorPalette update method."""

    def test_update_with_valid_hex(self) -> None:
        """Test updating with a valid hex color."""
        palette = ColorPalette()
        palette.update("residential", "#FF5733")
        assert palette.palette["residential"] == "#FF5733"

    def test_update_with_valid_hex_alpha(self) -> None:
        """Test updating with a valid hex color with alpha."""
        palette = ColorPalette()
        palette.update("residential", "#FF5733CC")
        assert palette.palette["residential"] == "#FF5733CC"

    def test_update_with_none(self) -> None:
        """Test that None generates a new color."""
        palette = ColorPalette()
        palette.update("residential", None)
        assert "residential" in palette.palette
        assert palette.palette["residential"] is not None

    def test_update_with_invalid_string(self) -> None:
        """Test that invalid color strings generate new colors."""
        palette = ColorPalette()
        palette.update("residential", "not_a_hex")
        assert "residential" in palette.palette
        assert palette.palette["residential"] != "not_a_hex"

    def test_update_non_string_key_raises_error(self) -> None:
        """Test that non-string keys raise TypeError."""
        palette = ColorPalette()
        with pytest.raises(TypeError, match="Key must be a string"):
            palette.update(123, "#FF5733")  # type: ignore[arg-type]

    def test_update_overwrites_existing(self) -> None:
        """Test that update overwrites existing colors."""
        palette = ColorPalette()
        palette.update("residential", "#FF5733")
        palette.update("residential", "#3498DB")
        assert palette.palette["residential"] == "#3498DB"


class TestColorPaletteGet:
    """Test ColorPalette get method."""

    def test_get_existing_color(self) -> None:
        """Test getting an existing color."""
        palette = ColorPalette()
        palette.update("residential", "#FF5733")
        color = palette.get("residential")
        assert color == "#FF5733"

    def test_get_nonexistent_generates_color(self) -> None:
        """Test that getting a nonexistent key generates a color."""
        palette = ColorPalette()
        color = palette.get("new_key")
        assert "new_key" in palette.palette
        assert color is not None
        assert len(color) > 0

    def test_get_multiple_times_returns_same_color(self) -> None:
        """Test that getting the same key multiple times returns the same color."""
        palette = ColorPalette()
        color1 = palette.get("residential")
        color2 = palette.get("residential")
        assert color1 == color2


class TestColorPalettePop:
    """Test ColorPalette pop method."""

    def test_pop_existing_key(self) -> None:
        """Test popping an existing key."""
        palette = ColorPalette()
        palette.update("residential", "#FF5733")
        color = palette.pop("residential")
        assert color == "#FF5733"
        assert "residential" not in palette.palette

    def test_pop_nonexistent_key_raises_error(self) -> None:
        """Test that popping a nonexistent key raises KeyError."""
        palette = ColorPalette()
        with pytest.raises(KeyError, match="unable to remove key"):
            palette.pop("nonexistent")


class TestColorPaletteFromDict:
    """Test ColorPalette.from_dict class method."""

    def test_from_dict_with_valid_colors(self) -> None:
        """Test creating palette from dict with valid colors."""
        colors = {
            "residential": "#FF5733",
            "commercial": "#3498DB",
            "industrial": "#2ECC71",
        }
        palette = ColorPalette.from_dict(colors)
        assert len(palette.palette) == 3
        assert palette.palette["residential"] == "#FF5733"
        assert palette.palette["commercial"] == "#3498DB"
        assert palette.palette["industrial"] == "#2ECC71"

    def test_from_dict_with_invalid_colors(self) -> None:
        """Test that invalid colors are replaced when loading from dict."""
        colors = {
            "residential": "not_a_color",
            "commercial": "#3498DB",
            "industrial": "also_not_a_color",
        }
        palette = ColorPalette.from_dict(colors)
        assert len(palette.palette) == 3
        assert palette.palette["commercial"] == "#3498DB"
        # Invalid colors should be replaced
        assert palette.palette["residential"] != "not_a_color"
        assert palette.palette["industrial"] != "also_not_a_color"

    def test_from_dict_empty(self) -> None:
        """Test creating palette from empty dict."""
        palette = ColorPalette.from_dict({})
        assert len(palette.palette) == 0


class TestColorPaletteToDict:
    """Test ColorPalette.to_dict method."""

    def test_to_dict_empty(self) -> None:
        """Test converting empty palette to dict."""
        palette = ColorPalette()
        result = palette.to_dict()
        assert isinstance(result, dict)
        assert len(result) == 0

    def test_to_dict_with_colors(self) -> None:
        """Test converting palette with colors to dict."""
        palette = ColorPalette()
        palette.update("residential", "#FF5733")
        palette.update("commercial", "#3498DB")
        result = palette.to_dict()
        assert len(result) == 2
        assert result["residential"] == "#FF5733"
        assert result["commercial"] == "#3498DB"

    def test_to_dict_returns_copy(self) -> None:
        """Test that to_dict returns a copy, not the original dict."""
        palette = ColorPalette()
        palette.update("residential", "#FF5733")
        result = palette.to_dict()
        result["new_key"] = "#000000"
        assert "new_key" not in palette.palette


class TestColorPaletteRoundTrip:
    """Test round-trip serialization/deserialization."""

    def test_round_trip_preserves_colors(self) -> None:
        """Test that to_dict and from_dict preserve colors."""
        original = ColorPalette()
        original.update("residential", "#FF5733")
        original.update("commercial", "#3498DB")
        original.update("industrial", "#2ECC71")

        # Serialize and deserialize
        dict_repr = original.to_dict()
        restored = ColorPalette.from_dict(dict_repr)

        # Check all colors are preserved
        assert len(restored.palette) == len(original.palette)
        for key in original.palette:
            assert restored.palette[key] == original.palette[key]


class TestColorPaletteColorGeneration:
    """Test color generation behavior."""

    def test_auto_generation_creates_unique_colors(self) -> None:
        """Test that auto-generated colors are different."""
        palette = ColorPalette()
        color1 = palette.get("key1")
        color2 = palette.get("key2")
        color3 = palette.get("key3")

        # Colors should be different (most of the time)
        # Note: There's a small chance they could be the same if the cycle repeats
        colors = [color1, color2, color3]
        assert len(set(colors)) >= 2  # At least 2 should be different

    def test_multiple_palettes_independent(self) -> None:
        """Test that multiple palette instances are independent."""
        palette1 = ColorPalette()
        palette2 = ColorPalette()

        palette1.update("residential", "#FF5733")
        palette2.update("residential", "#3498DB")

        assert palette1.get("residential") == "#FF5733"
        assert palette2.get("residential") == "#3498DB"


class TestColorPaletteHexValidation:
    """Test hex color validation."""

    def test_valid_6_digit_hex(self) -> None:
        """Test that 6-digit hex colors are accepted."""
        palette = ColorPalette()
        palette.update("test", "#FF5733")
        assert palette.palette["test"] == "#FF5733"

    def test_valid_8_digit_hex(self) -> None:
        """Test that 8-digit hex colors (with alpha) are accepted."""
        palette = ColorPalette()
        palette.update("test", "#FF5733CC")
        assert palette.palette["test"] == "#FF5733CC"

    def test_lowercase_hex(self) -> None:
        """Test that lowercase hex colors are accepted."""
        palette = ColorPalette()
        palette.update("test", "#ff5733")
        assert palette.palette["test"] == "#ff5733"

    def test_mixed_case_hex(self) -> None:
        """Test that mixed case hex colors are accepted."""
        palette = ColorPalette()
        palette.update("test", "#Ff5733")
        assert palette.palette["test"] == "#Ff5733"

    def test_invalid_short_hex(self) -> None:
        """Test that short hex colors are rejected."""
        palette = ColorPalette()
        palette.update("test", "#F57")
        # Should be replaced with auto-generated color
        assert palette.palette["test"] != "#F57"

    def test_invalid_no_hash(self) -> None:
        """Test that colors without # are rejected."""
        palette = ColorPalette()
        palette.update("test", "FF5733")
        assert palette.palette["test"] != "FF5733"

    def test_invalid_non_hex_chars(self) -> None:
        """Test that non-hex characters are rejected."""
        palette = ColorPalette()
        palette.update("test", "#GGGGGG")
        assert palette.palette["test"] != "#GGGGGG"
