from pathlib import Path
import re

import pandas as pd
import pytest
import shutil
from click.testing import CliRunner
from chronify.exceptions import InvalidOperation, InvalidParameter
from pytest import TempPathFactory

from stride import Project
from stride.models import Scenario
from stride.project import CONFIG_FILE
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
def test_override_calculated_table(
    tmp_path_factory: TempPathFactory, default_project: Project, file_ext: str
) -> None:
    tmp_path = tmp_path_factory.mktemp("tmpdir")
    new_path = tmp_path / "project2"
    shutil.copytree(default_project.path, new_path)
    project = Project.load(new_path)
    try:
        orig_total = (
            project.get_energy_projection()
            .filter("sector = 'residential' and scenario = 'alternate_gdp'")
            .to_df()["value"]
            .sum()
        )
    finally:
        project.close()

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
    assert "true" not in result.stdout

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
    project2 = Project.load(new_path, read_only=True)
    try:
        new_total = (
            project2.get_energy_projection()
            .filter("sector = 'residential' and scenario = 'alternate_gdp'")
            .to_df()["value"]
            .sum()
        )
        assert new_total == orig_total * 3
    finally:
        project2.close()

    cmd = ["calculated-tables", "list", str(project2.path)]
    result = runner.invoke(cli, cmd)
    assert result.exit_code == 0
    found = False
    regex = re.compile(r"energy_projection_res_load_shapes.*true")
    for line in result.stdout.splitlines():
        if regex.search(line) is not None:
            found = True
    assert found

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
    project3 = Project.load(new_path)
    try:
        with pytest.raises(InvalidOperation):
            project3.override_calculated_table(
                "alternate_gdp",
                "energy_projection_res_load_shapes_override",
                data_file,
            )
        with pytest.raises(InvalidParameter):
            project3.override_calculated_table(
                "invalid_scenario",
                "energy_projection_res_load_shapes",
                data_file,
            )
        with pytest.raises(InvalidParameter):
            project3.override_calculated_table("alternate_gdp", "invalid_calc_table", data_file)
    finally:
        project3.close()


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
    project2 = Project.load(new_path)
    try:
        with pytest.raises(InvalidParameter):
            project2.override_calculated_table(
                "alternate_gdp",
                "energy_projection_res_load_shapes",
                out_file,
            )
    finally:
        project2.close()


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
    project2 = Project.load(new_path)
    try:
        with pytest.raises(InvalidParameter):
            project2.override_calculated_table(
                "alternate_gdp",
                "energy_projection_res_load_shapes",
                data_file,
            )
    finally:
        project2.close()
