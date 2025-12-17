"""Project management utilities for STRIDE dashboard."""

import json
from pathlib import Path
from typing import Any

from loguru import logger

from stride.project import CONFIG_FILE, Project


def get_stride_projects_dir() -> Path:
    """
    Get the STRIDE projects directory from config or default location.

    Returns
    -------
    Path
        Path to the projects directory
    """
    # Check if there's a config file with projects directory
    config_dir = Path.home() / ".stride"
    config_file = config_dir / "config.json"

    if config_file.exists():
        try:
            with open(config_file) as f:
                config = json.load(f)
                if "projects_dir" in config:
                    return Path(config["projects_dir"])
        except Exception as e:
            logger.warning(f"Error reading config file: {e}")

    # Default to current working directory
    return Path.cwd()


def set_stride_projects_dir(projects_dir: Path) -> None:
    """
    Set the STRIDE projects directory in config.

    Parameters
    ----------
    projects_dir : Path
        Path to the projects directory
    """
    config_dir = Path.home() / ".stride"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_file = config_dir / "config.json"

    # Load existing config or create new one
    config = {}
    if config_file.exists():
        try:
            with open(config_file) as f:
                config = json.load(f)
        except Exception as e:
            logger.warning(f"Error reading config file: {e}")

    config["projects_dir"] = str(projects_dir.absolute())

    with open(config_file, "w") as f:
        json.dump(config, f, indent=2)

    logger.info(f"Set projects directory to: {projects_dir}")


def discover_projects(search_dirs: list[Path] | None = None) -> list[dict[str, Any]]:
    """
    Discover available STRIDE projects.

    Searches for directories containing project.json5 files.

    Parameters
    ----------
    search_dirs : list[Path] | None, optional
        Directories to search. If None, searches current directory and configured projects dir.

    Returns
    -------
    list[dict[str, Any]]
        List of project info dictionaries with keys:
        - name: project name
        - path: path to project directory
        - project_id: project ID from config
    """
    if search_dirs is None:
        search_dirs = [Path.cwd(), get_stride_projects_dir()]

    projects: list[dict[str, Any]] = []
    seen_paths: set[Path] = set()

    for search_dir in search_dirs:
        if not search_dir.exists():
            continue

        # Search current directory
        if (search_dir / CONFIG_FILE).exists():
            _add_project_if_valid(search_dir, projects, seen_paths)

        # Search subdirectories (one level deep)
        try:
            for subdir in search_dir.iterdir():
                if subdir.is_dir() and (subdir / CONFIG_FILE).exists():
                    _add_project_if_valid(subdir, projects, seen_paths)
        except PermissionError:
            logger.warning(f"Permission denied accessing: {search_dir}")
            continue

    return projects


def _add_project_if_valid(
    project_path: Path,
    projects: list[dict[str, Any]],
    seen_paths: set[Path],
) -> None:
    """
    Add a project to the list if it's valid and not already seen.

    Parameters
    ----------
    project_path : Path
        Path to the project directory
    projects : list[dict[str, Any]]
        List to append project info to
    seen_paths : set[Path]
        Set of already seen project paths
    """
    try:
        # Resolve to absolute path to avoid duplicates
        abs_path = project_path.resolve()

        if abs_path in seen_paths:
            return

        # Try to load project config to validate
        config_file = abs_path / CONFIG_FILE
        if not config_file.exists():
            return

        # Read the config to get project info
        from stride.models import ProjectConfig

        config = ProjectConfig.from_file(config_file)

        projects.append(
            {
                "name": config.project_id,
                "path": str(abs_path),
                "project_id": config.project_id,
                "display_name": config.project_id,  # Can be customized later
            }
        )

        seen_paths.add(abs_path)
        logger.debug(f"Found project: {config.project_id} at {abs_path}")

    except Exception as e:
        logger.debug(f"Invalid project at {project_path}: {e}")


def load_project_by_path(project_path: str | Path, **kwargs: Any) -> Project:
    """
    Load a STRIDE project by path.

    Parameters
    ----------
    project_path : str | Path
        Path to the project directory
    **kwargs
        Additional arguments to pass to Project.load()

    Returns
    -------
    Project
        Loaded project instance
    """
    return Project.load(project_path, **kwargs)


def get_recent_projects(max_count: int = 5) -> list[dict[str, Any]]:
    """
    Get recently accessed projects from config.

    Parameters
    ----------
    max_count : int, optional
        Maximum number of recent projects to return

    Returns
    -------
    list[dict[str, Any]]
        List of recent project info dictionaries
    """
    config_dir = Path.home() / ".stride"
    config_file = config_dir / "config.json"

    if not config_file.exists():
        return []

    try:
        with open(config_file) as f:
            config = json.load(f)
            recent: list[dict[str, Any]] = config.get("recent_projects", [])
            return recent[:max_count]
    except Exception as e:
        logger.warning(f"Error reading recent projects: {e}")
        return []


def add_recent_project(project_path: str | Path, project_id: str) -> None:
    """
    Add a project to the recent projects list.

    Parameters
    ----------
    project_path : str | Path
        Path to the project directory
    project_id : str
        Project ID
    """
    config_dir = Path.home() / ".stride"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_file = config_dir / "config.json"

    # Load existing config or create new one
    config = {}
    if config_file.exists():
        try:
            with open(config_file) as f:
                config = json.load(f)
        except Exception as e:
            logger.warning(f"Error reading config file: {e}")

    recent = config.get("recent_projects", [])

    # Remove if already exists
    recent = [p for p in recent if p["path"] != str(Path(project_path).absolute())]

    # Add to front
    recent.insert(
        0,
        {
            "path": str(Path(project_path).absolute()),
            "project_id": project_id,
            "name": project_id,
        },
    )

    # Keep only last 10
    config["recent_projects"] = recent[:10]

    with open(config_file, "w") as f:
        json.dump(config, f, indent=2)
