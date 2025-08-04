from pathlib import Path

import pytest
from click.testing import CliRunner
from pytest import TempPathFactory

from stride.cli.stride import cli
from stride.project import Project

TEST_PROJECT_CONFIG = Path("tests") / "data" / "project_input.json5"


@pytest.fixture(scope="session")
def project_config_file() -> Path:
    return TEST_PROJECT_CONFIG


@pytest.fixture
def default_project(tmp_path_factory: TempPathFactory) -> Project:
    """Create the default test project.
    Callers must not mutate any data because this is a shared fixture.
    """
    tmp_path = tmp_path_factory.mktemp("tmpdir")
    project_dir = tmp_path / "test_project"
    assert not project_dir.exists()
    cmd = ["projects", "create", str(TEST_PROJECT_CONFIG), "--directory", str(tmp_path)]
    runner = CliRunner()
    result = runner.invoke(cli, cmd)
    assert result.exit_code == 0
    assert project_dir.exists()
    return Project.load(project_dir)
