from pathlib import Path
from typing import Generator

import pytest
from click.testing import CliRunner
from pytest import TempPathFactory

from stride.cli.stride import cli
from stride.project import Project

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
    project = Project.load(project_dir, read_only=True)
    try:
        yield project
    finally:
        project.close()
