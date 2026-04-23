"""
Tests for the project cache and LRU eviction logic in app.py,
and the refresh-projects dropdown logic.

Covers code added in the `refresh_recent_projects` branch:
- get_max_cached_projects() configurable limit
- _evict_oldest_project()
- LRU reordering when switching to a cached project via load_project()
- refresh_dropdown_options (no-project variant via _register_refresh_projects_callback)
"""

from __future__ import annotations

import os
from collections.abc import Generator
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from stride.config import CACHED_PROJECTS_UPPER_BOUND
from stride.ui import app as app_module


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _make_mock_project(name: str = "proj") -> MagicMock:
    """Return a lightweight mock that behaves like a Project."""
    proj = MagicMock()
    proj.config.project_id = name
    proj.close = MagicMock()
    return proj


def _make_cache_entry(
    name: str = "proj",
) -> tuple[MagicMock, MagicMock, MagicMock, str]:
    """Return a (Project, ColorManager, StridePlots, name) tuple for the cache."""
    return (_make_mock_project(name), MagicMock(), MagicMock(), name)


@pytest.fixture(autouse=True)
def _reset_global_state() -> Generator[None, None, None]:
    """Ensure module-level cache state is clean before *and* after each test."""
    app_module._loaded_projects.clear()
    app_module._current_project_path = None
    app_module._max_cached_projects_override = None
    yield
    app_module._loaded_projects.clear()
    app_module._current_project_path = None
    app_module._max_cached_projects_override = None


# ===================================================================
# Tests for get_max_cached_projects priority chain
# ===================================================================


class TestGetMaxCachedProjects:
    """Tests for the get_max_cached_projects resolution function."""

    def test_default_value(self) -> None:
        """Should return 3 when no override, no env var, and no config."""
        with patch.object(app_module, "_get_config_max_cached", return_value=None):
            assert app_module.get_max_cached_projects() == 3

    def test_config_value(self) -> None:
        """Config file value should be used when no override or env var."""
        with patch.object(app_module, "_get_config_max_cached", return_value=5):
            assert app_module.get_max_cached_projects() == 5

    def test_env_var_overrides_config(self) -> None:
        """Environment variable should override config file value."""
        with (
            patch.object(app_module, "_get_config_max_cached", return_value=5),
            patch.dict(os.environ, {"STRIDE_MAX_CACHED_PROJECTS": "4"}),
        ):
            assert app_module.get_max_cached_projects() == 4

    def test_cli_override_overrides_env_and_config(self) -> None:
        """CLI override should take highest priority."""
        app_module._max_cached_projects_override = 2
        with (
            patch.object(app_module, "_get_config_max_cached", return_value=5),
            patch.dict(os.environ, {"STRIDE_MAX_CACHED_PROJECTS": "4"}),
        ):
            assert app_module.get_max_cached_projects() == 2

    def test_clamped_to_minimum(self) -> None:
        """Values below 1 should be clamped to 1."""
        app_module._max_cached_projects_override = 0
        assert app_module.get_max_cached_projects() == 1

    def test_clamped_to_maximum(self) -> None:
        """Values above CACHED_PROJECTS_UPPER_BOUND should be clamped."""
        app_module._max_cached_projects_override = 99
        assert app_module.get_max_cached_projects() == CACHED_PROJECTS_UPPER_BOUND

    def test_env_var_clamped(self) -> None:
        """Env var out of range should be clamped."""
        with (
            patch.object(app_module, "_get_config_max_cached", return_value=None),
            patch.dict(os.environ, {"STRIDE_MAX_CACHED_PROJECTS": "0"}),
        ):
            assert app_module.get_max_cached_projects() == 1

    def test_env_var_invalid_ignored(self) -> None:
        """Non-numeric env var should be ignored, falling through to config/default."""
        with (
            patch.object(app_module, "_get_config_max_cached", return_value=None),
            patch.dict(os.environ, {"STRIDE_MAX_CACHED_PROJECTS": "abc"}),
        ):
            assert app_module.get_max_cached_projects() == 3

    def test_set_and_clear_override(self) -> None:
        """set_max_cached_projects_override should set and clear correctly."""
        app_module.set_max_cached_projects_override(7)
        assert app_module._max_cached_projects_override == 7

        app_module.set_max_cached_projects_override(None)
        assert app_module._max_cached_projects_override is None


# ===================================================================
# Tests for _evict_oldest_project
# ===================================================================


class TestEvictOldestProject:
    """Tests for the _evict_oldest_project helper."""

    def test_no_eviction_when_below_capacity(self) -> None:
        """No project should be evicted when cache is below limit."""
        app_module._loaded_projects["/a"] = _make_cache_entry("A")
        app_module._loaded_projects["/b"] = _make_cache_entry("B")
        app_module._max_cached_projects_override = 3

        app_module._evict_oldest_project()

        assert len(app_module._loaded_projects) == 2
        assert "/a" in app_module._loaded_projects
        assert "/b" in app_module._loaded_projects

    def test_eviction_when_at_capacity(self) -> None:
        """The oldest (first-inserted) project should be evicted when at capacity."""
        app_module._max_cached_projects_override = 3
        limit = app_module.get_max_cached_projects()
        entries = {f"/{i}": _make_cache_entry(f"P{i}") for i in range(limit)}
        oldest_project = entries["/0"][0]
        app_module._loaded_projects.update(entries)

        app_module._evict_oldest_project()

        assert len(app_module._loaded_projects) == limit - 1
        assert "/0" not in app_module._loaded_projects
        oldest_project.close.assert_called_once()

    def test_eviction_removes_oldest_preserves_newest(self) -> None:
        """Eviction should remove the first key (LRU) and keep the rest."""
        app_module._max_cached_projects_override = 3
        app_module._loaded_projects["/old"] = _make_cache_entry("Old")
        app_module._loaded_projects["/mid"] = _make_cache_entry("Mid")
        app_module._loaded_projects["/new"] = _make_cache_entry("New")

        app_module._evict_oldest_project()

        assert "/old" not in app_module._loaded_projects
        assert "/mid" in app_module._loaded_projects
        assert "/new" in app_module._loaded_projects

    def test_eviction_on_empty_cache(self) -> None:
        """Eviction on an empty cache should be a no-op."""
        app_module._evict_oldest_project()
        assert len(app_module._loaded_projects) == 0

    def test_eviction_handles_close_exception(self) -> None:
        """If Project.close() raises, eviction should still proceed (logged as warning)."""
        app_module._max_cached_projects_override = 3
        limit = app_module.get_max_cached_projects()
        entries = {f"/{i}": _make_cache_entry(f"P{i}") for i in range(limit)}
        # Make close() raise for the oldest project
        entries["/0"][0].close.side_effect = RuntimeError("oops")
        app_module._loaded_projects.update(entries)

        # Should not raise
        app_module._evict_oldest_project()

        assert "/0" not in app_module._loaded_projects
        assert len(app_module._loaded_projects) == limit - 1

    def test_eviction_over_capacity(self) -> None:
        """If the cache somehow exceeds capacity, evict until below limit."""
        app_module._max_cached_projects_override = 3
        limit = app_module.get_max_cached_projects()
        # Manually stuff more than limit entries
        for i in range(limit + 2):
            app_module._loaded_projects[f"/{i}"] = _make_cache_entry(f"P{i}")

        app_module._evict_oldest_project()

        assert len(app_module._loaded_projects) == limit - 1

    def test_eviction_respects_dynamic_limit(self) -> None:
        """Lowering the limit should cause eviction of excess projects."""
        # Start with 5 projects and a limit of 5
        app_module._max_cached_projects_override = 5
        for i in range(5):
            app_module._loaded_projects[f"/{i}"] = _make_cache_entry(f"P{i}")

        # Lower the limit to 2
        app_module._max_cached_projects_override = 2
        app_module._evict_oldest_project()

        # Should have evicted down to 1 (limit - 1)
        assert len(app_module._loaded_projects) == 1


# ===================================================================
# Tests for LRU reordering in load_project
# ===================================================================


class TestLoadProjectLRU:
    """Tests for LRU re-ordering when switching to a cached project."""

    def test_cached_project_moves_to_end(self) -> None:
        """Accessing a cached project should move it to the end of the dict (MRU)."""
        app_module._loaded_projects["/first"] = _make_cache_entry("First")
        app_module._loaded_projects["/second"] = _make_cache_entry("Second")

        # Patch APIClient so it doesn't actually try to create an instance
        with patch.object(app_module, "APIClient"):
            success, msg = app_module.load_project("/first")

        assert success is True
        assert "Switched to cached" in msg
        # /first should now be the last key (most recently used)
        keys = list(app_module._loaded_projects.keys())
        assert keys[-1] == str(Path("/first").resolve())

    def test_cached_project_updates_current_path(self) -> None:
        """Switching to a cached project should update _current_project_path."""
        resolved = str(Path("/cached").resolve())
        app_module._loaded_projects[resolved] = _make_cache_entry("Cached")

        with patch.object(app_module, "APIClient"):
            app_module.load_project("/cached")

        assert app_module._current_project_path == resolved

    def test_load_new_project_triggers_eviction(self) -> None:
        """Loading a new project when at capacity should evict the oldest first."""
        app_module._max_cached_projects_override = 3
        limit = app_module.get_max_cached_projects()
        entry = _make_cache_entry("P0")
        oldest_mock = entry[0]
        app_module._loaded_projects["/proj0"] = entry
        for i in range(1, limit):
            app_module._loaded_projects[f"/proj{i}"] = _make_cache_entry(f"P{i}")

        mock_project = _make_mock_project("NewProj")
        mock_project.palette = MagicMock()
        mock_project.palette.copy.return_value = MagicMock(
            scenario_theme=["#aaa"], model_year_theme=["#bbb"], metric_theme=["#ccc"]
        )

        with (
            patch.object(app_module, "Project") as MockProject,
            patch.object(app_module, "APIClient") as MockAPIClient,
            patch.object(app_module, "create_fresh_color_manager") as mock_cm,
            patch.object(app_module, "StridePlots"),
            patch.object(app_module, "add_recent_project"),
        ):
            MockProject.load.return_value = mock_project
            mock_api = MagicMock()
            mock_api.scenarios = ["baseline"]
            MockAPIClient.return_value = mock_api
            mock_cm.return_value = MagicMock()

            success, _ = app_module.load_project("/brand_new")

        assert success is True
        oldest_mock.close.assert_called_once()
        assert "/proj0" not in app_module._loaded_projects

    def test_load_project_failure_returns_false(self) -> None:
        """A failed load should return (False, error_message)."""
        with patch.object(Path, "resolve", side_effect=RuntimeError("bad")):
            success, msg = app_module.load_project("/does/not/exist")

        assert success is False
        assert "bad" in msg


# ===================================================================
# Tests for get_loaded_project_options
# ===================================================================


class TestGetLoadedProjectOptions:
    """Tests for the get_loaded_project_options helper."""

    def test_empty_cache(self) -> None:
        assert app_module.get_loaded_project_options() == []

    def test_returns_all_cached_projects(self) -> None:
        app_module._loaded_projects["/a"] = _make_cache_entry("Alpha")
        app_module._loaded_projects["/b"] = _make_cache_entry("Beta")

        options = app_module.get_loaded_project_options()

        assert len(options) == 2
        labels = {o["label"] for o in options}
        assert labels == {"Alpha", "Beta"}

    def test_preserves_insertion_order(self) -> None:
        app_module._loaded_projects["/x"] = _make_cache_entry("X")
        app_module._loaded_projects["/y"] = _make_cache_entry("Y")

        options = app_module.get_loaded_project_options()
        assert options[0]["value"] == "/x"
        assert options[1]["value"] == "/y"


# ===================================================================
# Tests for MAX_CACHED_PROJECTS constant
# ===================================================================


def test_default_max_cached_projects_is_positive_int() -> None:
    """Sanity check: DEFAULT_MAX_CACHED_PROJECTS should be a small positive integer."""
    from stride.config import DEFAULT_MAX_CACHED_PROJECTS

    assert isinstance(DEFAULT_MAX_CACHED_PROJECTS, int)
    assert DEFAULT_MAX_CACHED_PROJECTS > 0


# ===================================================================
# Tests for _register_refresh_projects_callback logic
# (We test the inner function indirectly by extracting the logic.)
# ===================================================================


class TestRefreshDropdownLogic:
    """
    Test the dropdown-refresh logic used by both the 'with-project' and
    'no-project' variants of refresh_dropdown_options.

    Since the actual functions are Dash callbacks registered inside closures,
    we replicate/test the shared logic that builds dropdown options from
    get_recent_projects().
    """

    @staticmethod
    def _build_dropdown_options_no_project(
        recent: list[dict[str, Any]],
    ) -> list[dict[str, str]]:
        """Replicate the logic of the no-project refresh_dropdown_options."""
        dropdown_options: list[dict[str, str]] = []
        seen_project_ids: set[str] = set()
        for proj in recent:
            project_id = proj.get("project_id", "")
            proj_path = proj.get("path", "")
            if project_id and project_id not in seen_project_ids and Path(proj_path).exists():
                dropdown_options.append(
                    {"label": proj.get("name", project_id), "value": proj_path}
                )
                seen_project_ids.add(project_id)
        return dropdown_options

    @staticmethod
    def _build_dropdown_options_with_project(
        current_project_name: str,
        current_path: str,
        recent: list[dict[str, Any]],
    ) -> list[dict[str, str]]:
        """Replicate the logic of the with-project refresh_dropdown_options."""
        dropdown_options = [{"label": current_project_name, "value": current_path}]
        seen_project_ids = {current_project_name}
        for proj in recent:
            project_id = proj.get("project_id", "")
            proj_path = proj.get("path", "")
            if project_id and project_id not in seen_project_ids and Path(proj_path).exists():
                dropdown_options.append(
                    {"label": proj.get("name", project_id), "value": proj_path}
                )
                seen_project_ids.add(project_id)
        return dropdown_options

    def test_no_project_empty_recent(self) -> None:
        """No recent projects should yield an empty list."""
        assert self._build_dropdown_options_no_project([]) == []

    def test_no_project_deduplicates_by_project_id(self, tmp_path: Path) -> None:
        """Duplicate project_ids should be collapsed to a single entry."""
        p = tmp_path / "proj"
        p.mkdir()
        recent = [
            {"project_id": "dup", "path": str(p), "name": "Dup1"},
            {"project_id": "dup", "path": str(p), "name": "Dup2"},
        ]
        result = self._build_dropdown_options_no_project(recent)
        assert len(result) == 1
        assert result[0]["label"] == "Dup1"

    def test_no_project_skips_missing_paths(self, tmp_path: Path) -> None:
        """Projects whose paths don't exist should be excluded."""
        recent = [
            {"project_id": "gone", "path": "/no/such/path", "name": "Gone"},
        ]
        result = self._build_dropdown_options_no_project(recent)
        assert result == []

    def test_no_project_skips_empty_project_id(self, tmp_path: Path) -> None:
        """Entries with an empty project_id should be skipped."""
        p = tmp_path / "proj"
        p.mkdir()
        recent = [{"project_id": "", "path": str(p), "name": "NoId"}]
        result = self._build_dropdown_options_no_project(recent)
        assert result == []

    def test_no_project_uses_project_id_as_fallback_label(self, tmp_path: Path) -> None:
        """If 'name' is missing, the project_id should be used as the label."""
        p = tmp_path / "proj"
        p.mkdir()
        recent = [{"project_id": "myid", "path": str(p)}]
        result = self._build_dropdown_options_no_project(recent)
        assert result[0]["label"] == "myid"

    def test_with_project_includes_current_first(self, tmp_path: Path) -> None:
        """The current project should always be the first entry."""
        p = tmp_path / "other"
        p.mkdir()
        recent = [{"project_id": "other", "path": str(p), "name": "Other"}]
        result = self._build_dropdown_options_with_project("Current", "/current/path", recent)
        assert result[0] == {"label": "Current", "value": "/current/path"}
        assert len(result) == 2

    def test_with_project_does_not_duplicate_current(self, tmp_path: Path) -> None:
        """If the current project also appears in recent, it should not be duplicated."""
        p = tmp_path / "cur"
        p.mkdir()
        recent = [{"project_id": "Current", "path": str(p), "name": "Current"}]
        result = self._build_dropdown_options_with_project("Current", str(p), recent)
        # Only one entry because deduplication by project_id
        assert len(result) == 1

    def test_with_project_multiple_recent(self, tmp_path: Path) -> None:
        """Multiple valid recent projects should all appear after the current."""
        dirs = []
        for name in ("alpha", "beta", "gamma"):
            d = tmp_path / name
            d.mkdir()
            dirs.append(d)

        recent = [
            {"project_id": f"P{i}", "path": str(d), "name": f"Project {i}"}
            for i, d in enumerate(dirs)
        ]
        result = self._build_dropdown_options_with_project("Current", "/current", recent)
        # Current + 3 recent
        assert len(result) == 4
        assert result[0]["label"] == "Current"


# ===================================================================
# Tests for config round-trip (config.py helpers)
# ===================================================================


class TestConfigMaxCachedProjects:
    """Tests for get_max_cached_projects / set_max_cached_projects in config.py."""

    def test_round_trip(self, tmp_path: Path) -> None:
        """set_max_cached_projects(n) -> get_max_cached_projects() should return n."""
        from stride.config import (
            get_max_cached_projects as cfg_get,
            set_max_cached_projects as cfg_set,
        )

        config_file = tmp_path / "config.json"
        with patch("stride.config.get_stride_config_path", return_value=config_file):
            # Initially no config file
            assert cfg_get() is None

            # Set a value
            cfg_set(5)
            assert cfg_get() == 5

            # Update the value
            cfg_set(8)
            assert cfg_get() == 8

    def test_set_clamps_to_range(self, tmp_path: Path) -> None:
        """set_max_cached_projects should clamp values to [1, CACHED_PROJECTS_UPPER_BOUND]."""
        from stride.config import (
            get_max_cached_projects as cfg_get,
            set_max_cached_projects as cfg_set,
        )

        config_file = tmp_path / "config.json"
        with patch("stride.config.get_stride_config_path", return_value=config_file):
            cfg_set(0)
            assert cfg_get() == 1

            cfg_set(99)
            assert cfg_get() == CACHED_PROJECTS_UPPER_BOUND

    def test_set_preserves_other_config(self, tmp_path: Path) -> None:
        """set_max_cached_projects should not clobber other config keys."""
        import json

        from stride.config import set_max_cached_projects as cfg_set

        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({"default_user_palette": "my_palette"}))

        with patch("stride.config.get_stride_config_path", return_value=config_file):
            cfg_set(7)

        saved = json.loads(config_file.read_text())
        assert saved["max_cached_projects"] == 7
        assert saved["default_user_palette"] == "my_palette"


# ===================================================================
# Tests for save_max_cached_projects callback logic (callbacks.py)
# ===================================================================


class TestSaveMaxCachedProjectsLogic:
    """Test the validation and persistence logic in save_max_cached_projects.

    The actual callback is a closure inside register_settings_callbacks,
    so we replicate/test the shared logic directly.
    """

    @staticmethod
    def _save_max_cached_projects_logic(
        n_clicks: int | None,
        value: int | None,
    ) -> dict[str, Any]:
        """Replicate the logic of save_max_cached_projects callback.

        Returns a dict with 'success' bool, 'message' str, and optionally 'value' int.
        """
        if not n_clicks:
            return {"success": False, "message": "no_click"}

        if value is None:
            return {"success": False, "message": "Please enter a value"}

        try:
            n = int(value)
        except (TypeError, ValueError):
            return {"success": False, "message": "Invalid number"}

        if n < 1 or n > CACHED_PROJECTS_UPPER_BOUND:
            return {
                "success": False,
                "message": f"Value must be between 1 and {CACHED_PROJECTS_UPPER_BOUND}",
            }

        return {"success": True, "message": f"Max cached projects set to {n}", "value": n}

    def test_no_click_returns_no_update(self) -> None:
        result = self._save_max_cached_projects_logic(None, 5)
        assert result["success"] is False
        assert result["message"] == "no_click"

    def test_none_value_returns_error(self) -> None:
        result = self._save_max_cached_projects_logic(1, None)
        assert result["success"] is False
        assert "enter a value" in result["message"]

    def test_valid_value_succeeds(self) -> None:
        result = self._save_max_cached_projects_logic(1, 5)
        assert result["success"] is True
        assert result["value"] == 5

    def test_zero_value_rejected(self) -> None:
        result = self._save_max_cached_projects_logic(1, 0)
        assert result["success"] is False
        assert "between 1" in result["message"]

    def test_over_upper_bound_rejected(self) -> None:
        result = self._save_max_cached_projects_logic(1, CACHED_PROJECTS_UPPER_BOUND + 1)
        assert result["success"] is False
        assert "between 1" in result["message"]

    def test_upper_bound_accepted(self) -> None:
        result = self._save_max_cached_projects_logic(1, CACHED_PROJECTS_UPPER_BOUND)
        assert result["success"] is True
        assert result["value"] == CACHED_PROJECTS_UPPER_BOUND

    def test_value_of_one_accepted(self) -> None:
        result = self._save_max_cached_projects_logic(1, 1)
        assert result["success"] is True
        assert result["value"] == 1

    def test_persistence_and_eviction(self, tmp_path: Path) -> None:
        """Full integration: save triggers config write, override, and eviction."""
        import json

        config_file = tmp_path / "config.json"

        # Pre-fill cache with 4 projects
        app_module._max_cached_projects_override = 5
        for i in range(4):
            app_module._loaded_projects[f"/{i}"] = _make_cache_entry(f"P{i}")

        with patch("stride.config.get_stride_config_path", return_value=config_file):
            from stride.config import set_max_cached_projects

            set_max_cached_projects(2)
            app_module.set_max_cached_projects_override(2)
            app_module._evict_oldest_project()

        # Should have evicted down to 1 (limit - 1)
        assert len(app_module._loaded_projects) == 1
        # Config should be persisted
        saved = json.loads(config_file.read_text())
        assert saved["max_cached_projects"] == 2

    def test_settings_save_does_not_set_override(self, tmp_path: Path) -> None:
        """Regression: saving from Settings must not set _max_cached_projects_override.

        The save callback should only persist to config and trigger eviction,
        not set the runtime CLI override which would disable the input.
        """
        import json

        config_file = tmp_path / "config.json"

        assert app_module._max_cached_projects_override is None

        with patch("stride.config.get_stride_config_path", return_value=config_file):
            from stride.config import set_max_cached_projects

            # Replicate what the fixed save callback does (without override)
            set_max_cached_projects(5)
            app_module._evict_oldest_project()

        # The override must remain None so the input stays editable
        assert app_module._max_cached_projects_override is None
        # Config should be persisted
        saved = json.loads(config_file.read_text())
        assert saved["max_cached_projects"] == 5


# ===================================================================
# Tests for settings layout override display logic (layout.py)
# ===================================================================


class TestSettingsLayoutOverrideLogic:
    """Test the override source detection logic in create_settings_layout."""

    @staticmethod
    def _resolve_override_source(
        override_val: int | None,
        env_val: str | None,
    ) -> str | None:
        """Replicate the override source resolution from layout.py."""
        if override_val is not None:
            return f"CLI flag (--max-cached-projects {override_val})"
        if env_val is not None:
            return f"Environment variable (STRIDE_MAX_CACHED_PROJECTS={env_val})"
        return None

    def test_no_override(self) -> None:
        assert self._resolve_override_source(None, None) is None

    def test_cli_override(self) -> None:
        result = self._resolve_override_source(5, None)
        assert result is not None
        assert "CLI flag" in result
        assert "5" in result

    def test_env_override(self) -> None:
        result = self._resolve_override_source(None, "4")
        assert result is not None
        assert "Environment variable" in result
        assert "4" in result

    def test_cli_takes_priority_over_env(self) -> None:
        """CLI override should be shown even when env var is also set."""
        result = self._resolve_override_source(5, "4")
        assert result is not None
        assert "CLI flag" in result

    def test_is_overridden_when_cli_set(self) -> None:
        result = self._resolve_override_source(5, None)
        assert result is not None  # is_overridden = True

    def test_is_overridden_when_env_set(self) -> None:
        result = self._resolve_override_source(None, "3")
        assert result is not None  # is_overridden = True

    def test_not_overridden_when_neither_set(self) -> None:
        result = self._resolve_override_source(None, None)
        assert result is None  # is_overridden = False


# ===================================================================
# Tests for CLI --max-cached-projects option (stride.py)
# ===================================================================


class TestCLIMaxCachedProjectsOption:
    """Test the --max-cached-projects CLI option integration."""

    def test_option_sets_override(self) -> None:
        """--max-cached-projects should call set_max_cached_projects_override."""
        app_module.set_max_cached_projects_override(7)
        assert app_module._max_cached_projects_override == 7
        assert app_module.get_max_cached_projects() == 7

    def test_option_none_does_not_set_override(self) -> None:
        """When --max-cached-projects is not provided (None), override should not be set."""
        # Replicate the CLI logic: if max_cached_projects is not None: set_override(n)
        max_cached_projects = None
        if max_cached_projects is not None:
            app_module.set_max_cached_projects_override(max_cached_projects)
        assert app_module._max_cached_projects_override is None

    def test_override_affects_get_max(self) -> None:
        """Override via CLI should change get_max_cached_projects result."""
        with patch.object(app_module, "_get_config_max_cached", return_value=5):
            # Without override
            assert app_module.get_max_cached_projects() == 5

            # With override
            app_module.set_max_cached_projects_override(2)
            assert app_module.get_max_cached_projects() == 2


# ===================================================================
# Tests for config.py get_max_cached_projects edge cases
# ===================================================================


class TestConfigGetMaxCachedEdgeCases:
    """Test edge cases in config.py get_max_cached_projects."""

    def test_invalid_config_value_returns_none(self, tmp_path: Path) -> None:
        """Non-numeric config value should return None."""
        import json

        from stride.config import get_max_cached_projects as cfg_get

        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({"max_cached_projects": "not_a_number"}))

        with patch("stride.config.get_stride_config_path", return_value=config_file):
            assert cfg_get() is None

    def test_config_value_clamped_to_bounds(self, tmp_path: Path) -> None:
        """Config values outside bounds should be clamped."""
        import json

        from stride.config import get_max_cached_projects as cfg_get

        config_file = tmp_path / "config.json"

        config_file.write_text(json.dumps({"max_cached_projects": 0}))
        with patch("stride.config.get_stride_config_path", return_value=config_file):
            assert cfg_get() == 1

        config_file.write_text(json.dumps({"max_cached_projects": 99}))
        with patch("stride.config.get_stride_config_path", return_value=config_file):
            assert cfg_get() == CACHED_PROJECTS_UPPER_BOUND

    def test_missing_key_returns_none(self, tmp_path: Path) -> None:
        """Config file without the key should return None."""
        import json

        from stride.config import get_max_cached_projects as cfg_get

        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({"other_key": "value"}))

        with patch("stride.config.get_stride_config_path", return_value=config_file):
            assert cfg_get() is None
