from typing import Any

from stride.models import ProjectConfig


def create_dsgrid_project(config: ProjectConfig) -> dict[str, Any]:
    """Create a default dsgrid project config."""
    # TODO: The only part of this project currently used is the time dimension.
    # We are not yet sure if we will use a dsgrid project.
    project: dict[str, Any] = {
        "project_id": config.project_id,
        "name": config.project_id,
        "description": config.description,
        "datasets": [],
        "dimensions": {
            "base_dimensions": [
                {
                    "type": "scenario",
                    "class": "Scenario",
                    "name": "default",
                    "description": "Default scenario",
                    "records": [{"id": "default", "name": "default"}],
                },
                {
                    "type": "model_year",
                    "class": "ModelYear",
                    "name": "model_year",
                    "description": "Model years",
                    "records": [
                        {"id": str(x), "name": str(x)}
                        for x in range(
                            config.start_year,
                            config.end_year + 1,
                            config.step_year,
                        )
                    ],
                },
                {
                    "type": "weather_year",
                    "class": "WeatherYear",
                    "name": "weather_year",
                    "description": "Selected weather year",
                    "records": [
                        {"id": "2018", "name": str(config.weather_year)},
                    ],
                },
                {
                    "type": "geography",
                    "class": "Geography",
                    "name": "country",
                    "description": "Selected country",
                    "records": [
                        {
                            "id": config.country,
                            "name": config.country,
                            "time_zone": "EasternStandard",
                        },
                    ],
                },
                {
                    "type": "sector",
                    "class": "Sector",
                    "name": "sector",
                    "description": "Industrial, residential, and transportation sectors",
                    "records": [
                        {"id": "industrial", "name": "Industrial"},
                        {"id": "residential", "name": "Residential"},
                        {"id": "transportation", "name": "Transportation"},
                    ],
                },
                {
                    "type": "subsector",
                    "class": "Subsector",
                    "name": "subsector",
                    "description": "unspecified",
                    "records": [
                        {"id": "unspecified", "name": "Unspecified"},
                    ],
                },
                {
                    "type": "metric",
                    "class": "EnergyEndUse",
                    "name": "end_use",
                    "description": "Temporary placeholder for annual energy",
                    "records": [
                        {
                            "id": "total",
                            "name": "Total",
                            "fuel_id": "electricity",
                            "unit": "MWh",
                        },
                        {
                            "id": "cooling",
                            "name": "Cooling",
                            "fuel_id": "electricity",
                            "unit": "MWh",
                        },
                        {
                            "id": "other",
                            "name": "Other",
                            "fuel_id": "electricity",
                            "unit": "MWh",
                        },
                    ],
                },
                {
                    "type": "metric",
                    "class": "Population",
                    "name": "population",
                    "description": "Number of people",
                    "records": [{"id": "population", "name": "Population", "unit": "people"}],
                },
                {
                    "type": "metric",
                    "class": "FractionalIndex",
                    "name": "hdi",
                    "description": "Human Development Index",
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
                {
                    "type": "metric",
                    "class": "Stock",
                    "name": "gdp",
                    "description": "Gross Domestic Product",
                    "records": [{"id": "gdp", "name": "GDP", "unit": "billion USD-2024"}],
                },
                {
                    "type": "metric",
                    "class": "EnergyIntensityRegression",
                    "name": "energy_intensity_regression",
                    "description": "Energy intensity regression coefficients for linear and exponential fits",
                    "records": [
                        {
                            "id": "res_a0_lin",
                            "name": "Residential Intercept Linear",
                            "regression_type": "linear",
                            "unit": "TJ/HDI-person",
                        },
                        {
                            "id": "res_a1_lin",
                            "name": "Residential Slope Linear",
                            "regression_type": "linear",
                            "unit": "TJ/HDI-person-yr",
                        },
                        {
                            "id": "res_t0_lin",
                            "name": "Residential Start Year Linear",
                            "regression_type": "linear",
                            "unit": "yr",
                        },
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
                            "id": "res_t0_exp",
                            "name": "Residential Start Year Exponential",
                            "regression_type": "exponential",
                            "unit": "yr",
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
                            "id": "nonres_t0_lin",
                            "name": "Non-residential Start Year Linear",
                            "regression_type": "linear",
                            "unit": "yr",
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
                        {
                            "id": "nonres_t0_exp",
                            "name": "Non-residential Start Year Exponential",
                            "regression_type": "exponential",
                            "unit": "yr",
                        },
                    ],
                },
                {
                    "class": "Time",
                    "frequency": "P0DT1H0M0.000000S",
                    "name": "time_est",
                    "time_type": "datetime",
                    "leap_day_adjustment": "none",
                    "description": "Time dimension, 2018 hourly EST",
                    "time_interval_type": "period_beginning",
                    "str_format": "%Y-%m-%d %H:%M:%S",
                    "timezone": "EasternStandard",
                    "measurement_type": "total",
                    "type": "time",
                    "ranges": [
                        {
                            "start": "2018-01-01 00:00:00",
                            "end": "2018-12-31 23:00:00",
                        },
                    ],
                },
            ],
            "supplemental_dimensions": [],
        },
    }
    for scenario in config.scenarios:
        project["datasets"].extend(
            [
                {
                    "dataset_id": f"{scenario.name}__energy_intensity",
                    "dataset_type": "modeled",
                    "version": "1.0.0",
                    "required_dimensions": {
                        "single_dimensional": {
                            "metric": {
                                "base": {
                                    "record_ids": [],
                                    "dimension_name": "energy_intensity_regression",
                                }
                            }
                        },
                    },
                },
                {
                    "dataset_id": f"{scenario.name}__gdp",
                    "dataset_type": "modeled",
                    "version": "1.0.0",
                    "required_dimensions": {
                        "single_dimensional": {
                            "metric": {"base": {"record_ids": [], "dimension_name": "gdp"}}
                        },
                    },
                },
                {
                    "dataset_id": f"{scenario.name}__hdi",
                    "dataset_type": "modeled",
                    "version": "1.0.0",
                    "required_dimensions": {
                        "single_dimensional": {
                            "metric": {"base": {"record_ids": [], "dimension_name": "hdi"}}
                        },
                    },
                },
                {
                    "dataset_id": f"{scenario.name}__population",
                    "dataset_type": "modeled",
                    "version": "1.0.0",
                    "required_dimensions": {
                        "single_dimensional": {
                            "metric": {"base": {"record_ids": [], "dimension_name": "population"}}
                        },
                    },
                },
                {
                    "dataset_id": f"{scenario.name}__load_shapes",
                    "dataset_type": "modeled",
                    "version": "1.0.0",
                    "required_dimensions": {
                        "single_dimensional": {
                            "metric": {"base": {"record_ids": [], "dimension_name": "end_use"}}
                        },
                    },
                },
            ]
        )
    return project
