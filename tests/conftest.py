import shutil
from pathlib import Path
from typing import Generator
import pytest
from click.testing import CliRunner
from pytest import TempPathFactory

from stride.cli.stride import cli
from stride.project import Project
from stride.api import APIClient

TEST_PROJECT_CONFIG = Path("tests") / "data" / "project_input.json5"


@pytest.fixture(scope="session")
def project_config_file() -> Path:
    return TEST_PROJECT_CONFIG


@pytest.fixture(scope="session")
def default_project(
    tmp_path_factory: TempPathFactory, project_config_file: Path
) -> Generator[Project, None, None]:
    """Create the default test project.
    Callers must not mutate any data because this is a shared fixture.
    """
    tmp_path = tmp_path_factory.mktemp("tmpdir")
    project_dir = tmp_path / "test_project"
    assert not project_dir.exists()
    cmd = ["projects", "create", str(project_config_file), "--directory", str(tmp_path)]
    runner = CliRunner()
    result = runner.invoke(cli, cmd)
    assert result.exit_code == 0
    assert project_dir.exists()
    with Project.load(project_dir, read_only=True) as project:
        yield project


@pytest.fixture(scope="session")
def api_client(default_project: Project) -> APIClient:
    """Create APIClient instance with session-scoped test project."""
    # Reset singleton to ensure clean state
    APIClient._instance = None
    client = APIClient(project=default_project)
    return client


@pytest.fixture
def copy_project_input_data(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Create a copy of the input data for the test project.

    Returns
    -------
    tuple[Path, Path, Path]
        (scratch directory for temp files, base directory of the inputs, project config file)
    """
    project_dir = tmp_path / "project_inputs"
    shutil.copytree(TEST_PROJECT_CONFIG.parent, project_dir)
    return tmp_path, project_dir, project_dir / "project_input.json5"
