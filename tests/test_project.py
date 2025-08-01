import pytest
import shutil
from click.testing import CliRunner

from stride import Project
from stride.models import Scenario
from stride.project import CONFIG_FILE
from stride.cli.stride import cli


@pytest.fixture(scope="module")
def default_project(tmp_path_factory, project_config_file) -> Project:
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
    return Project.load(project_dir)


def test_has_table(default_project: Project) -> None:
    project = default_project
    assert project.has_table("energy_projection")
    assert project.has_table("energy_projection", schema="baseline")
    assert project.has_table("energy_projection", schema="alternate_gdp")


def test_list_scenarios(default_project: Project) -> None:
    project = default_project
    assert project.list_scenarios() == ["baseline", "alternate_gdp"]


def test_show_dataset(default_project: Project) -> None:
    project = default_project
    runner = CliRunner()
    result = runner.invoke(cli, ["datasets", "list"])
    assert result.exit_code == 0
    dataset_ids = result.stdout.split()
    assert dataset_ids
    for dataset_id in dataset_ids:
        result = runner.invoke(
            cli, ["datasets", "show", str(project.path), dataset_id, "-l", "10"]
        )
        assert result.exit_code == 0
        assert "country_1" in result.stdout


def test_scenario_name() -> None:
    for name in (
        "dsgrid_data",
        "dsgrid_lookup",
        "dsgrid_missing_associations",
        "stride",
        "default",
    ):
        with pytest.raises(ValueError):
            Scenario(name=name)
        Scenario(name="allowed")


def test_invalid_load(tmp_path, default_project: Project) -> None:
    project = default_project
    new_path = tmp_path / "project2"
    shutil.copytree(project.path, new_path)
    runner = CliRunner()
    result = runner.invoke(cli, ["scenarios", "list", str(new_path)])
    assert result.exit_code == 0
    assert "baseline" in result.stdout
    assert "alternate_gdp" in result.stdout
    (new_path / CONFIG_FILE).unlink()
    runner = CliRunner()
    result = runner.invoke(cli, ["scenarios", "list", str(new_path)])
    assert result.exit_code != 0
