from pathlib import Path

import pandas as pd
import pytest
import shutil
from click.testing import CliRunner
from chronify.exceptions import InvalidOperation, InvalidParameter
from dsgrid.utils.files import dump_json_file, load_json_file
from pytest import TempPathFactory

from stride import Project
from stride.dataset_download import get_default_data_directory
from stride.models import CalculatedTableOverride, ProjectConfig, Scenario
from stride.project import (
    CONFIG_FILE,
    _get_base_and_override_names,
    generate_project_template,
    list_valid_countries,
    list_valid_model_years,
    list_valid_weather_years,
    validate_country,
)
from stride.cli.stride import cli


def test_has_table(default_project: Project) -> None:
    project = default_project
    assert project.has_table("energy_projection")
    assert project.has_table("energy_projection", schema="baseline")
    assert project.has_table("energy_projection", schema="alternate_gdp")


def test_list_scenarios(default_project: Project) -> None:
    project = default_project
    assert project.list_scenario_names() == ["baseline", "ev_projection", "alternate_gdp"]


def test_show_data_table(default_project: Project) -> None:
    project = default_project
    runner = CliRunner()
    result = runner.invoke(cli, ["data-tables", "list"])
    assert result.exit_code == 0
    data_table_ids = result.stdout.split()
    assert data_table_ids
    for data_table_id in data_table_ids:
        result = runner.invoke(
            cli, ["data-tables", "show", str(project.path), data_table_id, "-l", "10"]
        )
        assert result.exit_code == 0


def test_show_data_table_filters_by_country(default_project: Project) -> None:
    """Test that data-tables show filters by the project's country.

    The test project uses country_1, so gdp data should only show country_1,
    not country_2 (which also exists in the global-test dataset).
    """
    project = default_project
    runner = CliRunner()
    # The test project is configured for country_1
    assert project.config.country == "country_1"
    # Show gdp data - should only show country_1 data
    result = runner.invoke(cli, ["data-tables", "show", str(project.path), "gdp", "-l", "100"])
    assert result.exit_code == 0
    # country_1 should appear in the output (it's the project's country)
    assert "country_1" in result.stdout
    # country_2 should NOT appear - the data should be filtered by project country
    assert "country_2" not in result.stdout


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
    assert "country_1" in result.stdout or "country_2" in result.stdout


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
        "--dataset",
        "global-test",
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
    # alternate_gdp scenario is at index 2 (after baseline and ev_projection)
    orig = config["scenarios"][2]["gdp"]
    config["scenarios"][2]["gdp"] += "invalid.csv"
    dump_json_file(config, project_config_file)
    with pytest.raises(InvalidParameter, match=r"Scenario.*dataset.*does not exist"):
        ProjectConfig.from_file(project_config_file)

    config["scenarios"][2]["gdp"] = orig
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


def test_get_valid_countries() -> None:
    """Test that get_valid_countries returns the expected countries from the test dataset."""
    dataset_dir = get_default_data_directory() / "global-test"
    countries = list_valid_countries(dataset_dir)
    assert "country_1" in countries
    assert "country_2" in countries
    assert len(countries) == 2


def test_get_valid_countries_missing_file(tmp_path: Path) -> None:
    """Test that get_valid_countries raises an error if the project.json5 file is missing."""
    with pytest.raises(InvalidParameter, match="Dataset project file not found"):
        list_valid_countries(tmp_path)


def test_validate_country_valid() -> None:
    """Test that validate_country succeeds for a valid country."""
    dataset_dir = get_default_data_directory() / "global-test"
    validate_country("country_1", dataset_dir)
    validate_country("country_2", dataset_dir)


def test_validate_country_invalid() -> None:
    """Test that validate_country raises an error for an invalid country."""
    dataset_dir = get_default_data_directory() / "global-test"
    with pytest.raises(InvalidParameter, match="Country 'InvalidCountry' is not available"):
        validate_country("InvalidCountry", dataset_dir)


def test_create_project_invalid_country(copy_project_input_data: tuple[Path, Path, Path]) -> None:
    """Test that project creation fails early with an invalid country."""
    tmp_path, _, project_config_file = copy_project_input_data
    config = load_json_file(project_config_file)
    config["country"] = "NonExistentCountry"
    dump_json_file(config, project_config_file)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "projects",
            "create",
            str(project_config_file),
            "-d",
            str(tmp_path),
            "--dataset",
            "global-test",
        ],
    )
    assert result.exit_code != 0
    assert "NonExistentCountry" in result.output
    assert "not available" in result.output


def test_create_project_case_insensitive_country(
    copy_project_input_data: tuple[Path, Path, Path],
) -> None:
    """Test that project creation works with case-mismatched country name."""
    tmp_path, _, project_config_file = copy_project_input_data
    config = load_json_file(project_config_file)
    # Use uppercase country name (dataset has "country_1")
    config["country"] = "COUNTRY_1"
    dump_json_file(config, project_config_file)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "projects",
            "create",
            str(project_config_file),
            "-d",
            str(tmp_path),
            "--dataset",
            "global-test",
        ],
    )
    assert result.exit_code == 0, f"Project creation failed: {result.output}"
    # Verify the project was created with the correctly-cased country name
    project_dir = tmp_path / config["project_id"]
    assert project_dir.exists()
    created_config = load_json_file(project_dir / "project.json5")
    # The country should be normalized to the dataset's casing
    assert created_config["country"] == "country_1"


def test_create_project_with_data_dir(copy_project_input_data: tuple[Path, Path, Path]) -> None:
    """Test that project creation works with --data-dir option and uses the specified directory."""
    tmp_path, _, project_config_file = copy_project_input_data

    runner = CliRunner()
    # Use the default data directory path explicitly via --data-dir
    data_dir = get_default_data_directory()
    result = runner.invoke(
        cli,
        [
            "projects",
            "create",
            str(project_config_file),
            "-d",
            str(tmp_path),
            "--dataset",
            "global-test",
            "--data-dir",
            str(data_dir),
        ],
    )
    assert result.exit_code == 0
    # Verify the custom data directory was actually used by checking log output
    # The log message "Registered dsgrid project and datasets from {path}" confirms the path
    expected_dataset_path = data_dir / "global-test"
    assert str(expected_dataset_path) in result.output, (
        f"Expected dataset path '{expected_dataset_path}' not found in output. "
        f"Output was: {result.output}"
    )


def test_create_project_with_invalid_data_dir(
    copy_project_input_data: tuple[Path, Path, Path],
) -> None:
    """Test that project creation fails with invalid --data-dir."""
    tmp_path, _, project_config_file = copy_project_input_data

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "projects",
            "create",
            str(project_config_file),
            "-d",
            str(tmp_path),
            "--dataset",
            "global-test",
            "--data-dir",
            "/nonexistent/path",
        ],
    )
    assert result.exit_code != 0
    assert "Dataset directory not found" in result.output


def test_projects_init_command(tmp_path: Path) -> None:
    """Test that 'stride projects init' creates a project template."""
    output_file = tmp_path / "my_project.json5"
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "projects",
            "init",
            "--country",
            "Germany",
            "-o",
            str(output_file),
        ],
    )
    assert result.exit_code == 0
    assert output_file.exists()
    content = output_file.read_text()
    assert "germany_project" in content
    assert 'country: "Germany"' in content
    assert "start_year: 2025" in content
    assert "end_year: 2050" in content
    assert '"baseline"' in content
    assert '"ev_projection"' in content
    assert "use_ev_projection: true" in content


def test_projects_init_command_custom_project_id(tmp_path: Path) -> None:
    """Test 'stride projects init' with custom project ID."""
    output_file = tmp_path / "custom.json5"
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "projects",
            "init",
            "--country",
            "Chile",
            "--project-id",
            "my_custom_id",
            "-o",
            str(output_file),
        ],
    )
    assert result.exit_code == 0
    content = output_file.read_text()
    assert "my_custom_id" in content
    assert 'country: "Chile"' in content


def test_projects_init_command_no_overwrite(tmp_path: Path) -> None:
    """Test that 'stride projects init' fails without --overwrite if file exists."""
    output_file = tmp_path / "existing.json5"
    output_file.write_text("{}")

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "projects",
            "init",
            "--country",
            "Germany",
            "-o",
            str(output_file),
        ],
    )
    assert result.exit_code != 0
    assert "already exists" in result.output


def test_projects_init_command_with_overwrite(tmp_path: Path) -> None:
    """Test that 'stride projects init' works with --overwrite."""
    output_file = tmp_path / "existing.json5"
    output_file.write_text("{}")

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "projects",
            "init",
            "--country",
            "Germany",
            "-o",
            str(output_file),
            "--overwrite",
        ],
    )
    assert result.exit_code == 0
    content = output_file.read_text()
    assert "germany_project" in content


def test_generate_project_template() -> None:
    """Test generate_project_template function."""
    content = generate_project_template(country="TestCountry", project_id="test_id")
    assert "test_id" in content
    assert 'country: "TestCountry"' in content
    assert "start_year" in content
    assert "end_year" in content
    assert "weather_year" in content
    assert "baseline" in content
    assert "ev_projection" in content
    assert "use_ev_projection: true" in content


def test_validate_country_case_insensitive() -> None:
    """Test that validate_country works case-insensitively and returns correct case."""
    dataset_dir = get_default_data_directory() / "global-test"
    # Test lowercase input returns correctly-cased output
    result = validate_country("country_1", dataset_dir)
    assert result == "country_1"
    # Test uppercase input (assuming dataset has country_1)
    result = validate_country("COUNTRY_1", dataset_dir)
    assert result == "country_1"
    # Test mixed case
    result = validate_country("Country_1", dataset_dir)
    assert result == "country_1"


def test_validate_country_returns_correct_case() -> None:
    """Test that validate_country returns the case from the dataset."""
    dataset_dir = get_default_data_directory() / "global-test"
    # The function should return the exact casing from the dataset
    result = validate_country("country_2", dataset_dir)
    assert result == "country_2"


def test_list_valid_model_years() -> None:
    """Test that list_valid_model_years returns model years from the dataset."""
    dataset_dir = get_default_data_directory() / "global-test"
    model_years = list_valid_model_years(dataset_dir)
    assert isinstance(model_years, list)
    assert len(model_years) > 0
    # Model years should be strings (IDs)
    for year in model_years:
        assert isinstance(year, str)


def test_list_valid_model_years_missing_file(tmp_path: Path) -> None:
    """Test that list_valid_model_years raises error for missing project.json5."""
    with pytest.raises(InvalidParameter, match="Dataset project file not found"):
        list_valid_model_years(tmp_path)


def test_list_valid_weather_years() -> None:
    """Test that list_valid_weather_years returns weather years from the dataset."""
    dataset_dir = get_default_data_directory() / "global-test"
    weather_years = list_valid_weather_years(dataset_dir)
    assert isinstance(weather_years, list)
    assert len(weather_years) > 0
    # Weather years should be strings (IDs)
    for year in weather_years:
        assert isinstance(year, str)


def test_list_valid_weather_years_missing_file(tmp_path: Path) -> None:
    """Test that list_valid_weather_years raises error for missing project.json5."""
    with pytest.raises(InvalidParameter, match="Dataset project file not found"):
        list_valid_weather_years(tmp_path)


def test_list_model_years_command() -> None:
    """Test the 'stride datasets list-model-years' CLI command."""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["datasets", "list-model-years", "-D", "global-test"],
    )
    assert result.exit_code == 0
    assert "Model years available" in result.output
    # Check that some known model years from the dataset are listed
    dataset_dir = get_default_data_directory() / "global-test"
    model_years = list_valid_model_years(dataset_dir)
    assert any(year in result.output for year in model_years)


def test_list_model_years_command_invalid_dataset() -> None:
    """Test that list-model-years fails gracefully for nonexistent dataset."""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["datasets", "list-model-years", "-D", "nonexistent-dataset"],
    )
    assert result.exit_code != 0
    assert "Dataset directory not found" in result.output


def test_list_weather_years_command() -> None:
    """Test the 'stride datasets list-weather-years' CLI command."""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["datasets", "list-weather-years", "-D", "global-test"],
    )
    assert result.exit_code == 0
    assert "Weather years available" in result.output


def test_list_weather_years_command_invalid_dataset() -> None:
    """Test that list-weather-years fails gracefully for nonexistent dataset."""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["datasets", "list-weather-years", "-D", "nonexistent-dataset"],
    )
    assert result.exit_code != 0
    assert "Dataset directory not found" in result.output


def test_list_countries_command() -> None:
    """Test the 'stride datasets list-countries' CLI command."""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["datasets", "list-countries", "-D", "global-test"],
    )
    assert result.exit_code == 0
    assert "Countries available" in result.output
    assert "country_1" in result.output
    assert "country_2" in result.output


def test_list_countries_command_invalid_dataset() -> None:
    """Test that list-countries fails gracefully for nonexistent dataset."""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["datasets", "list-countries", "-D", "nonexistent-dataset"],
    )
    assert result.exit_code != 0
    assert "Dataset directory not found" in result.output


def test_list_model_years_command_with_data_dir(tmp_path: Path) -> None:
    """Test list-model-years with custom --data-dir option."""
    runner = CliRunner()
    # Using a nonexistent path should fail
    result = runner.invoke(
        cli,
        ["datasets", "list-model-years", "--data-dir", str(tmp_path)],
    )
    assert result.exit_code != 0

    # Using the default data directory should succeed
    data_dir = get_default_data_directory()
    result = runner.invoke(
        cli,
        ["datasets", "list-model-years", "-D", "global-test", "--data-dir", str(data_dir)],
    )
    assert result.exit_code == 0


def test_list_weather_years_command_with_data_dir(tmp_path: Path) -> None:
    """Test list-weather-years with custom --data-dir option."""
    runner = CliRunner()
    # Using a nonexistent path should fail
    result = runner.invoke(
        cli,
        ["datasets", "list-weather-years", "--data-dir", str(tmp_path)],
    )
    assert result.exit_code != 0

    # Using the default data directory should succeed
    data_dir = get_default_data_directory()
    result = runner.invoke(
        cli,
        ["datasets", "list-weather-years", "-D", "global-test", "--data-dir", str(data_dir)],
    )
    assert result.exit_code == 0


def test_stride_data_dir_env_var() -> None:
    """Test that STRIDE_DATA_DIR environment variable is respected by CLI commands."""
    runner = CliRunner()
    data_dir = get_default_data_directory()

    # Test list-countries with STRIDE_DATA_DIR env var
    result = runner.invoke(
        cli,
        ["datasets", "list-countries", "-D", "global-test"],
        env={"STRIDE_DATA_DIR": str(data_dir)},
    )
    assert result.exit_code == 0
    assert "country_1" in result.output

    # Test that invalid STRIDE_DATA_DIR causes failure
    result = runner.invoke(
        cli,
        ["datasets", "list-countries", "-D", "global-test"],
        env={"STRIDE_DATA_DIR": "/nonexistent/path"},
    )
    assert result.exit_code != 0
    assert "Dataset directory not found" in result.output


def test_stride_data_dir_env_var_override() -> None:
    """Test that --data-dir option overrides STRIDE_DATA_DIR env var."""
    runner = CliRunner()
    data_dir = get_default_data_directory()

    # --data-dir should override STRIDE_DATA_DIR
    result = runner.invoke(
        cli,
        ["datasets", "list-countries", "-D", "global-test", "--data-dir", str(data_dir)],
        env={"STRIDE_DATA_DIR": "/nonexistent/path"},
    )
    assert result.exit_code == 0
    assert "country_1" in result.output


def test_create_project_with_env_var(copy_project_input_data: tuple[Path, Path, Path]) -> None:
    """Test that project creation uses STRIDE_DATA_DIR env var."""
    tmp_path, _, project_config_file = copy_project_input_data

    runner = CliRunner()
    data_dir = get_default_data_directory()
    result = runner.invoke(
        cli,
        [
            "projects",
            "create",
            str(project_config_file),
            "-d",
            str(tmp_path),
            "--dataset",
            "global-test",
        ],
        env={"STRIDE_DATA_DIR": str(data_dir)},
    )
    assert result.exit_code == 0
    # Verify the env var data directory was actually used by checking log output
    expected_dataset_path = data_dir / "global-test"
    assert str(expected_dataset_path) in result.output, (
        f"Expected dataset path '{expected_dataset_path}' not found in output. "
        f"Output was: {result.output}"
    )
