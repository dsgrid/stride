from pathlib import Path

import pandas as pd
import pytest
import shutil
from click.testing import CliRunner
from chronify.exceptions import InvalidOperation, InvalidParameter
from dsgrid.utils.files import dump_json_file, load_json_file
from pytest import TempPathFactory

from stride import Project
from stride.models import CalculatedTableOverride, ProjectConfig, Scenario
from stride.project import CONFIG_FILE, _get_base_and_override_names
from stride.cli.stride import cli


def test_has_table(default_project: Project) -> None:
    project = default_project
    assert project.has_table("energy_projection")
    assert project.has_table("energy_projection", schema="baseline")
    assert project.has_table("energy_projection", schema="alternate_gdp")


def test_list_scenarios(default_project: Project) -> None:
    project = default_project
    assert project.list_scenario_names() == ["baseline", "alternate_gdp"]


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


@pytest.mark.skip(reason="calculated tables are broken")
def test_show_calculated_table(default_project: Project) -> None:
    project = default_project
    runner = CliRunner()
    result = runner.invoke(cli, ["calculated-tables", "list", str(project.path)])
    assert result.exit_code == 0
    tables = [x.strip() for x in result.stdout.splitlines()][1:]
    assert tables
    result = runner.invoke(
        cli, ["calculated-tables", "show", str(project.path), tables[0], "-l", "10"]
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


def test_invalid_load(tmp_path: Path, default_project: Project) -> None:
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


@pytest.mark.parametrize("file_ext", [".csv", ".parquet"])
@pytest.mark.skip(reason="calculated tables are broken")
def test_override_calculated_table(
    tmp_path_factory: TempPathFactory, default_project: Project, file_ext: str
) -> None:
    tmp_path = tmp_path_factory.mktemp("tmpdir")
    new_path = tmp_path / "project2"
    shutil.copytree(default_project.path, new_path)
    with Project.load(new_path) as project:
        orig_total = (
            project.get_energy_projection()
            .filter("sector = 'residential' and scenario = 'alternate_gdp'")
            .to_df()["value"]
            .sum()
        )

    data_file = tmp_path / "data.parquet"
    cmd = [
        "calculated-tables",
        "export",
        str(new_path),
        "-s",
        "baseline",
        "-t",
        "energy_projection_res_load_shapes",
        "-f",
        str(data_file),
    ]
    runner = CliRunner()
    result = runner.invoke(cli, cmd)
    assert result.exit_code == 0

    cmd = ["calculated-tables", "list", str(new_path)]
    result = runner.invoke(cli, cmd)
    assert result.exit_code == 0
    assert "energy_projection_res_load_shapes_override" not in result.stdout

    df = pd.read_parquet(data_file)
    df["value"] *= 3
    if file_ext == ".csv":
        out_file = data_file.with_suffix(".csv")
        df.to_csv(out_file, header=True, index=False)
    else:
        out_file = data_file
        df.to_parquet(data_file)
    cmd = [
        "calculated-tables",
        "override",
        str(new_path),
        "-s",
        "alternate_gdp",
        "-t",
        "energy_projection_res_load_shapes",
        "-f",
        str(out_file),
    ]
    result = runner.invoke(cli, cmd)
    assert result.exit_code == 0
    with Project.load(new_path, read_only=True) as project2:
        new_total = (
            project2.get_energy_projection()
            .filter("sector = 'residential' and scenario = 'alternate_gdp'")
            .to_df()["value"]
            .sum()
        )
        assert new_total == orig_total * 3

    cmd = ["calculated-tables", "list", str(project2.path)]
    result = runner.invoke(cli, cmd)
    assert result.exit_code == 0
    assert "energy_projection_res_load_shapes_override" in result.stdout

    # Try to override an override table, which isn't allowed.
    data_file = tmp_path / "data.parquet"
    cmd = [
        "calculated-tables",
        "export",
        str(new_path),
        "-s",
        "baseline",
        "-t",
        "energy_projection_res_load_shapes_override",
        "-f",
        str(data_file),
        "--overwrite",
    ]
    result = runner.invoke(cli, cmd)
    assert result.exit_code == 0
    with Project.load(new_path) as project3:
        with pytest.raises(InvalidOperation):
            project3.override_calculated_tables(
                [
                    CalculatedTableOverride(
                        scenario="alternate_gdp",
                        table_name="energy_projection_res_load_shapes_override",
                        filename=data_file,
                    )
                ]
            )
        with pytest.raises(InvalidParameter):
            project3.override_calculated_tables(
                [
                    CalculatedTableOverride(
                        scenario="invalid_scenario",
                        table_name="energy_projection_res_load_shapes",
                        filename=data_file,
                    )
                ]
            )
        with pytest.raises(InvalidParameter):
            project3.override_calculated_tables(
                [
                    CalculatedTableOverride(
                        scenario="alternate_gdp",
                        table_name="invalid_calc_table",
                        filename=data_file,
                    )
                ]
            )

    cmd = [
        "calculated-tables",
        "remove-override",
        str(new_path),
        "-s",
        "alternate_gdp",
        "-t",
        "energy_projection_res_load_shapes_override",
    ]
    result = runner.invoke(cli, cmd)
    assert result.exit_code == 0

    cmd = ["calculated-tables", "list", str(project2.path)]
    result = runner.invoke(cli, cmd)
    assert result.exit_code == 0
    assert "energy_projection_res_load_shapes_override" not in result.stdout

    with Project.load(new_path) as project:
        new_total = (
            project.get_energy_projection()
            .filter("sector = 'residential' and scenario = 'alternate_gdp'")
            .to_df()["value"]
            .sum()
        )
        assert new_total == orig_total


@pytest.mark.skip(reason="calculated tables are broken")
def test_override_calculated_table_extra_column(
    tmp_path_factory: TempPathFactory, default_project: Project
) -> None:
    tmp_path = tmp_path_factory.mktemp("tmpdir")
    new_path = tmp_path / "project2"
    shutil.copytree(default_project.path, new_path)

    data_file = tmp_path / "data.parquet"
    cmd = [
        "calculated-tables",
        "export",
        str(new_path),
        "-s",
        "baseline",
        "-t",
        "energy_projection_res_load_shapes",
        "-f",
        str(data_file),
    ]
    runner = CliRunner()
    result = runner.invoke(cli, cmd)
    assert result.exit_code == 0

    df = pd.read_parquet(data_file)
    out_file = data_file.with_suffix(".csv")
    # The index columns makes this operation invalid.
    df.to_csv(out_file, header=True, index=True)
    with Project.load(new_path) as project2:
        with pytest.raises(InvalidParameter):
            project2.override_calculated_tables(
                [
                    CalculatedTableOverride(
                        scenario="alternate_gdp",
                        table_name="energy_projection_res_load_shapes",
                        filename=out_file,
                    )
                ]
            )


@pytest.mark.skip(reason="calculated tables are broken")
def test_override_calculated_table_mismatched_column(
    tmp_path_factory: TempPathFactory, default_project: Project
) -> None:
    tmp_path = tmp_path_factory.mktemp("tmpdir")
    new_path = tmp_path / "project2"
    shutil.copytree(default_project.path, new_path)

    data_file = tmp_path / "data.parquet"
    cmd = [
        "calculated-tables",
        "export",
        str(new_path),
        "-s",
        "baseline",
        "-t",
        "energy_projection_res_load_shapes",
        "-f",
        str(data_file),
    ]
    runner = CliRunner()
    result = runner.invoke(cli, cmd)
    assert result.exit_code == 0

    df = pd.read_parquet(data_file)
    df.rename(columns={"timestamp": "timestamp2"}, inplace=True)
    df.to_parquet(data_file, index=False)
    with Project.load(new_path) as project2:
        with pytest.raises(InvalidParameter):
            project2.override_calculated_tables(
                [
                    CalculatedTableOverride(
                        scenario="alternate_gdp",
                        table_name="energy_projection_res_load_shapes",
                        filename=data_file,
                    )
                ]
            )


@pytest.mark.skip(reason="calculated tables are broken")
def test_override_calculated_table_pre_registration(
    default_project: Project, copy_project_input_data: tuple[Path, Path, Path]
) -> None:
    tmp_path, _, project_config_file = copy_project_input_data
    orig_total = (
        default_project.get_energy_projection()
        .filter("sector = 'residential' and scenario = 'alternate_gdp'")
        .to_df()["value"]
        .sum()
    )
    data_file = tmp_path / "data.parquet"
    default_project.export_calculated_table(
        "baseline", "energy_projection_res_load_shapes", data_file
    )
    df = pd.read_parquet(data_file)
    df["value"] *= 3
    df.to_parquet(data_file)

    config = load_json_file(project_config_file)
    assert "calculated_table_overrides" not in config
    config["calculated_table_overrides"] = [
        {
            "scenario": "alternate_gdp",
            "table_name": "energy_projection_res_load_shapes",
            "filename": str(data_file.with_stem("invalid")),
        }
    ]
    dump_json_file(config, project_config_file)
    new_base_dir = tmp_path / "project2"
    new_base_dir.mkdir()
    cmd = [
        "projects",
        "create",
        str(project_config_file),
        "-d",
        str(new_base_dir),
    ]
    runner = CliRunner()
    result = runner.invoke(cli, cmd)
    assert result.exit_code != 0

    config = load_json_file(project_config_file)
    config["calculated_table_overrides"][0]["filename"] = str(data_file)
    dump_json_file(config, project_config_file)
    result = runner.invoke(cli, cmd)
    assert result.exit_code == 0

    with Project.load(new_base_dir / config["project_id"], read_only=True) as project:
        new_total = (
            project.get_energy_projection()
            .filter("sector = 'residential' and scenario = 'alternate_gdp'")
            .to_df()["value"]
            .sum()
        )
        assert new_total == orig_total * 3


def test_export_energy_projection(
    tmp_path_factory: TempPathFactory, default_project: Project
) -> None:
    tmp_path = tmp_path_factory.mktemp("tmpdir")
    filename = tmp_path / "energy_projection.parquet"
    assert not filename.exists()
    runner = CliRunner()
    cmd = [
        "projects",
        "export-energy-projection",
        str(default_project.path),
        "-f",
        str(filename),
    ]
    result = runner.invoke(cli, cmd)
    assert result.exit_code == 0
    assert filename.exists()


def test_invalid_data_tables(copy_project_input_data: tuple[Path, Path, Path]) -> None:
    project_config_file = copy_project_input_data[2]
    config = load_json_file(project_config_file)
    orig = config["scenarios"][1]["gdp"]
    config["scenarios"][1]["gdp"] += "invalid.csv"
    dump_json_file(config, project_config_file)
    with pytest.raises(InvalidParameter, match=r"Scenario.*dataset.*does not exist"):
        ProjectConfig.from_file(project_config_file)

    config["scenarios"][1]["gdp"] = orig
    config["calculated_table_overrides"] = [
        {
            "scenario": "alternate_gdp",
            "table_name": "energy_projection_res_load_shapes",
            "filename": "invalid.csv",
        }
    ]
    dump_json_file(config, project_config_file)
    with pytest.raises(InvalidParameter, match=r"Scenario.*calculated_table.*does not exist"):
        ProjectConfig.from_file(project_config_file)


def test_get_base_and_override_names() -> None:
    expected = ("energy_projection_res_load_shapes", "energy_projection_res_load_shapes_override")
    assert _get_base_and_override_names("energy_projection_res_load_shapes") == expected
    assert _get_base_and_override_names("energy_projection_res_load_shapes_override") == expected
    with pytest.raises(InvalidParameter):
        _get_base_and_override_names("load_shapes_override_override")
