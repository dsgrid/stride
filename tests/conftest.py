from pathlib import Path
import pytest
from click.testing import CliRunner
from pytest import TempPathFactory

from stride.cli.stride import cli
from stride.project import Project
from stride.api import APIClient

TEST_PROJECT_CONFIG = Path("tests") / "data" / "project_input.json5"


def _create_test_project(tmp_path_factory: TempPathFactory, project_name: str) -> Project:
    """Helper function to create a test project."""
    tmp_path = tmp_path_factory.mktemp(f"{project_name}_tmpdir")
    project_dir = tmp_path / project_name
    assert not project_dir.exists()
    cmd = ["projects", "create", str(TEST_PROJECT_CONFIG), "--directory", str(tmp_path)]
    runner = CliRunner()
    result = runner.invoke(cli, cmd)
    assert result.exit_code == 0
    assert project_dir.exists()
    return Project.load(project_dir)


@pytest.fixture(scope="session")
def project_config_file() -> Path:
    return TEST_PROJECT_CONFIG


@pytest.fixture
def default_project(tmp_path_factory: TempPathFactory) -> Project:
    """Create the default test project.
    Callers must not mutate any data because this is a shared fixture.
    """
    return _create_test_project(tmp_path_factory, "test_project")


@pytest.fixture(scope="session")
def scoped_default_project(tmp_path_factory: TempPathFactory) -> Project:
    """Create a session-scoped test project for fixtures that need session scope."""
    return _create_test_project(tmp_path_factory, "test_project_session")


@pytest.fixture(scope="session")
def api_client(scoped_default_project: Project) -> APIClient:
    """Create APIClient instance with session-scoped test project."""
    # Reset singleton to ensure clean state
    APIClient._instance = None
    client = APIClient(project=scoped_default_project)
    return client
