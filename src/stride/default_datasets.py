from pathlib import Path
from typing import Any

import pandas as pd
from dsgrid.dimension.base_models import DimensionType

import stride
from stride.models import DatasetConfig, ProjectConfig


def create_test_datasets(
    config: ProjectConfig, dsg_project: dict[str, Any]
) -> list[DatasetConfig]:
    """Create a list of default stride datasets for tests."""
    metrics_map = _make_metrics_map(dsg_project)
    data_path = Path(next(iter(stride.__path__))).parents[1] / "tests" / "data"
    ei_file = data_path / "energy_intensity.csv"
    gdp_file = data_path / "gdp.csv"
    hdi_file = data_path / "hdi.csv"
    population_file = data_path / "population.csv"
    load_shapes_file = data_path / "load_shapes.csv"
    defaults = {
        "energy_intensity": {
            "filename": ei_file,
            "df": pd.read_csv(ei_file),
            "func": energy_intensity_dataset,
        },
        "gdp": {
            "filename": gdp_file,
            "df": pd.read_csv(gdp_file),
            "func": gdp_dataset,
        },
        "hdi": {
            "filename": hdi_file,
            "df": pd.read_csv(hdi_file),
            "func": hdi_dataset,
        },
        "population": {
            "filename": population_file,
            "df": pd.read_csv(population_file),
            "func": population_dataset,
        },
        "load_shapes": {
            "filename": load_shapes_file,
            "df": pd.read_csv(load_shapes_file),
            "func": load_shapes_dataset,
        },
    }

    datasets: list[DatasetConfig] = []
    for scenario in config.scenarios:
        for key, val in defaults.items():
            scenario_file = getattr(scenario, key)
            if scenario_file is None:
                filename = val["filename"]
                df = val["df"]
            else:
                # TODO: this allows users to customize rows but not column names.
                # Also, no re-mapping of values.
                filename = scenario_file
                df = pd.read_csv(scenario_file)
            dataset = val["func"](scenario.name, metrics_map, filename, df)
            datasets.append(dataset)

    return datasets


def energy_intensity_dataset(
    scenario_name: str, metrics_map: dict[str, str], filename: Path, df: pd.DataFrame
) -> DatasetConfig:
    return DatasetConfig(
        dataset_id=f"{scenario_name}__energy_intensity",
        path=filename,
        metric_class="EnergyIntensityRegression",
        metric_dimension_name=metrics_map["EnergyIntensityRegression"],
        dimension_columns={
            "country": DimensionType.GEOGRAPHY,
            "metric": DimensionType.METRIC,
            "sector": DimensionType.SECTOR,
        },
        dimensions=[
            {
                "type": "geography",
                "class": "Geography",
                "name": "country",
                "description": "Energy intensity countries",
                "records": [{"id": x, "name": x} for x in df["country"].unique()],
            },
            {
                "type": "sector",
                "class": "Sector",
                "name": "sector",
                "description": "Energy intensity sectors",
                "records": [{"id": x, "name": x} for x in df["sector"].unique()],
            },
            {
                "type": "metric",
                "class": "EnergyIntensityRegression",
                "name": "energy_intensity_regression",
                "description": "EnergyIntensityRegression",
                "records": [
                    # {
                    #     "id": "res_a0_lin",
                    #     "name": "Residential Intercept Linear",
                    #     "regression_type": "linear",
                    #     "unit": "TJ/HDI-person",
                    # },
                    # {
                    #     "id": "res_a1_lin",
                    #     "name": "Residential Slope Linear",
                    #     "regression_type": "linear",
                    #     "unit": "TJ/HDI-person-yr",
                    # },
                    {
                        "id": "res_a0_exp",
                        "name": "Residential Intercept Exponential",
                        "regression_type": "exponential",
                        "unit": "TJ/HDI-person",
                    },
                    {
                        "id": "res_a1_exp",
                        "name": "Residential Slope Exponential",
                        "regression_type": "exponential",
                        "unit": "TJ/HDI-person-yr",
                    },
                    {
                        "id": "nonres_a0_lin",
                        "name": "Non-residential Intercept Linear",
                        "regression_type": "linear",
                        "unit": "TJ/billion USD-2024",
                    },
                    {
                        "id": "nonres_a1_lin",
                        "name": "Non-residential Slope Linear",
                        "regression_type": "linear",
                        "unit": "TJ/billion USD-2024-yr",
                    },
                    {
                        "id": "nonres_a0_exp",
                        "name": "Non-residential Intercept Exponential",
                        "regression_type": "exponential",
                        "unit": "TJ/billion USD-2024",
                    },
                    {
                        "id": "nonres_a1_exp",
                        "name": "Non-residential Slope Exponential",
                        "regression_type": "exponential",
                        "unit": "TJ/billion USD-2024-yr",
                    },
                ],
            },
        ],
    )


def gdp_dataset(
    scenario_name: str, metrics_map: dict[str, str], filename: Path, df: pd.DataFrame
) -> DatasetConfig:
    return DatasetConfig(
        dataset_id=f"{scenario_name}__gdp",
        path=filename,
        metric_class="Stock",
        metric_dimension_name=metrics_map["Stock"],
        dimension_columns={
            "country": DimensionType.GEOGRAPHY,
            "year": DimensionType.MODEL_YEAR,
        },
        trivial_dimensions=[DimensionType.METRIC],
        dimensions=[
            {
                "type": "geography",
                "class": "Geography",
                "name": "country",
                "description": "GDP countries",
                "records": [{"id": x, "name": x} for x in df["country"].unique()],
            },
            {
                "type": "model_year",
                "class": "ModelYear",
                "name": "model_year",
                "description": "GDP model years",
                "records": [{"id": str(x), "name": str(x)} for x in df["year"].unique()],
            },
            {
                "type": "metric",
                "class": "Stock",
                "name": "gdp",
                "description": "GDP",
                "records": [{"id": "stock", "name": "stock", "unit": "billion USD-2024"}],
            },
        ],
    )


def hdi_dataset(
    scenario_name: str, metrics_map: dict[str, str], filename: Path, df: pd.DataFrame
) -> DatasetConfig:
    return DatasetConfig(
        dataset_id=f"{scenario_name}__hdi",
        path=filename,
        metric_class="FractionalIndex",
        metric_dimension_name=metrics_map["FractionalIndex"],
        dimension_columns={
            "country": DimensionType.GEOGRAPHY,
            "year": DimensionType.MODEL_YEAR,
        },
        trivial_dimensions=[DimensionType.METRIC],
        dimensions=[
            {
                "type": "geography",
                "class": "Geography",
                "name": "country",
                "description": "HDI countries",
                "records": [{"id": x, "name": x} for x in df["country"].unique()],
            },
            {
                "type": "model_year",
                "class": "ModelYear",
                "name": "model_year",
                "description": "HDI model years",
                "records": [{"id": str(x), "name": str(x)} for x in df["year"].unique()],
            },
            {
                "type": "metric",
                "class": "FractionalIndex",
                "name": "hdi",
                "description": "HDI",
                "records": [
                    {
                        "id": "hdi",
                        "name": "HDI",
                        "unit": "HDI",
                        "min_value": 0.0,
                        "max_value": 1.0,
                    }
                ],
            },
        ],
    )


def population_dataset(
    scenario_name: str, metrics_map: dict[str, str], filename: Path, df: pd.DataFrame
) -> DatasetConfig:
    return DatasetConfig(
        dataset_id=f"{scenario_name}__population",
        path=filename,
        metric_class="Population",
        metric_dimension_name=metrics_map["Population"],
        dimension_columns={
            "country": DimensionType.GEOGRAPHY,
            "year": DimensionType.MODEL_YEAR,
        },
        trivial_dimensions=[DimensionType.METRIC],
        dimensions=[
            {
                "type": "geography",
                "class": "Geography",
                "name": "country",
                "description": "Population countries",
                "records": [{"id": x, "name": x} for x in df["country"].unique()],
            },
            {
                "type": "model_year",
                "class": "ModelYear",
                "name": "model_year",
                "description": "Population model years",
                "records": [{"id": str(x), "name": str(x)} for x in df["year"].unique()],
            },
            {
                "type": "metric",
                "class": "Population",
                "name": "population",
                "description": "Population",
                "records": [{"id": "population", "name": "population", "unit": "people"}],
            },
        ],
    )


def load_shapes_dataset(
    scenario_name: str, metrics_map: dict[str, str], filename: Path, df: pd.DataFrame
) -> DatasetConfig:
    return DatasetConfig(
        dataset_id=f"{scenario_name}__load_shapes",
        path=filename,
        metric_class="EnergyEndUse",
        metric_dimension_name=metrics_map["EnergyEndUse"],
        time_columns=["month", "is_weekday", "hour"],
        dimension_columns={
            "country": DimensionType.GEOGRAPHY,
            "sector": DimensionType.SECTOR,
            "enduse": DimensionType.METRIC,
            "year": DimensionType.WEATHER_YEAR,
        },
        trivial_dimensions=[
            DimensionType.SCENARIO,
            DimensionType.SUBSECTOR,
        ],
        dimensions=[
            {
                "type": "geography",
                "class": "Geography",
                "name": "country",
                "description": "Load shapes countries",
                "records": [
                    {"id": x, "name": x, "time_zone": "EasternStandard"}
                    for x in df["country"].unique()
                ],
            },
            {
                "type": "scenario",
                "class": "Scenario",
                "name": "scenario",
                "description": "Default scenario",
                "records": [{"id": "default", "name": "Default"}],
            },
            {
                "type": "sector",
                "class": "Sector",
                "name": "sector",
                "description": "Load shapes sectors",
                "records": [{"id": x, "name": x} for x in df["sector"].unique()],
            },
            {
                "type": "subsector",
                "class": "Subsector",
                "name": "subsector",
                "description": "Load shapes subsectors",
                "records": [{"id": "unspecified", "name": "Unspecified"}],
            },
            {
                "type": "weather_year",
                "class": "WeatherYear",
                "name": "weather_year",
                "description": "Weather Year 2018",
                "records": [{"id": str(x), "name": str(x)} for x in df["year"].unique()],
            },
            {
                "type": "metric",
                "class": "EnergyEndUse",
                "name": "end_use",
                "description": "Profiles",
                "records": [
                    {"id": x, "name": x, "unit": "MWh", "fuel_id": "electricity"}
                    for x in df["enduse"].unique()
                ],
            },
            {
                "class": "Time",
                "type": "time",
                "name": "hourly_for_representative_days",
                "ranges": [
                    {
                        "start": 1,
                        "end": 12,
                    },
                ],
                "time_interval_type": "period_ending",
                "time_type": "representative_period",
                "measurement_type": "total",
                "format": "one_weekday_day_and_one_weekend_day_per_month_by_hour",
                "description": "month, weekday/weekend, and hour of day.",
            },
        ],
    )


def _make_metrics_map(dsg_project: dict[str, Any]) -> dict[str, str]:
    metrics_map: dict[str, str] = {}
    for dim in dsg_project["dimensions"]["base_dimensions"]:
        if dim["type"] == "metric":
            assert dim["class"] not in metrics_map
            metrics_map[dim["class"]] = dim["name"]
    return metrics_map
