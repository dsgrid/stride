from enum import StrEnum
from pathlib import Path
from typing import Self

from chronify.exceptions import InvalidParameter
from pydantic import Field, field_validator

from dsgrid.data_models import DSGBaseModel


class DatasetType(StrEnum):
    ENERGY_BY_SECTOR = "energy_by_sector"
    ENERGY_INTENSITY_BY_SECTOR = "energy_intensity_by_sector"
    ENERGY_INTENSITY_REGRESSION_BY_SECTOR = "energy_intensity_regression_by_sector"
    GDP = "gdp"
    HDI = "hdi"
    POPULATION = "population"


class ProjectionSliceType(StrEnum):
    ENERGY_BY_SECTOR = "energy_by_sector"
    EVS = "evs"
    HEAT_PUMPS = "heat_pumps"


class Scenario(DSGBaseModel):  # type: ignore
    """Allows the user to add custom tables to compare against the defaults."""

    name: str = Field(description="Name of the scenario")
    energy_intensity: Path | None = Field(
        default=None,
        description="Optional path to a user-provided energy intensity table",
    )
    gdp: Path | None = Field(
        default=None,
        description="Optional path to a user-provided GDP table",
    )
    hdi: Path | None = Field(
        default=None,
        description="Optional path to a user-provided HDI table",
    )
    load_shapes: Path | None = Field(
        default=None,
        description="Optional path to a user-provided load shapes table",
    )
    population: Path | None = Field(
        default=None,
        description="Optional path to a user-provided population table",
    )
    weather_bait: Path | None = Field(
        default=None,
        description="Optional path to a user-provided weather_bait table",
    )
    electricity_per_vehicle_km_projections: Path | None = Field(
        default=None,
        description="Optional path to a user-provided population table",
    )
    ev_stock_share_projections: Path | None = Field(
        default=None,
        description="Optional path to a user-provided ev_stock_share_projections table",
    )
    km_per_vehicle_year_regressions: Path | None = Field(
        default=None,
        description="Optional path to a user-provided km_per_vehicle_year_regressions table",
    )
    phev_share_projections: Path | None = Field(
        default=None,
        description="Optional path to a user-provided phev_share_projections table",
    )
    vehicle_per_capita_regressions: Path | None = Field(
        default=None,
        description="Optional path to a user-provided vehicle_per_capita_regressions table",
    )

    @field_validator("name")
    @classmethod
    def check_name(cls, name: str) -> str:
        if name in (
            "dsgrid_data",
            "dsgrid_lookup",
            "dsgrid_missing_associations",
            "stride",
            "default",  # Not allowed by DuckDB
        ):
            msg = (
                f"A scenario name cannot be {name} because it conflicts with existing "
                "database schema names."
            )
            raise ValueError(msg)
        return name


class CalculatedTableOverride(DSGBaseModel):  # type: ignore
    """Defines an override for a calculated table in a scenario."""

    scenario: str = Field(description="Scenario name")
    table_name: str = Field(description="Base name of calculated table being overridden")
    filename: Path | None = Field(
        default=None, description="Path to file containing the override data."
    )


class ProjectConfig(DSGBaseModel):  # type: ignore
    """Defines a Stride project."""

    project_id: str = Field(description="Unique identifier for the project")
    creator: str = Field(description="Creator of the project")
    description: str = Field(description="Description of the project")
    country: str = Field(description="Country upon which the data is based")
    start_year: int = Field(description="Start year for the forecasted data")
    end_year: int = Field(description="End year for the forecasted data")
    step_year: int = Field(default=1, description="End year for the forecasted data")
    weather_year: int = Field(description="Weather year upon which the data is based")
    scenarios: list[Scenario] = Field(
        default=[Scenario(name="baseline")],
        description="Scenarios for the project. Users may add custom scenarios.",
        min_length=1,
    )
    calculated_table_overrides: list[CalculatedTableOverride] = Field(
        default=[],
        description="Calculated tables to override",
    )

    @classmethod
    def from_file(cls, filename: Path | str) -> Self:
        path = Path(filename)
        config = super().from_file(path)
        for scenario in config.scenarios:
            for field in Scenario.model_fields:
                if field != "name":
                    val = getattr(scenario, field)
                    if val is not None and not val.is_absolute():
                        setattr(scenario, field, path.parent / val)
                    val = getattr(scenario, field)
                    if val is not None and not val.exists():
                        msg = (
                            f"Scenario={scenario.name} dataset={field} filename={val} "
                            f"does not exist"
                        )
                        raise InvalidParameter(msg)
            for table in config.calculated_table_overrides:
                if table.filename is not None and not table.filename.is_absolute():
                    table.filename = path.parent / table.filename
                if table.filename is not None and not table.filename.exists():
                    msg = (
                        f"Scenario={scenario.name} calculated_table={table.table_name} "
                        f"filename={table.filename} does not exist"
                    )
                    raise InvalidParameter(msg)
        return config  # type: ignore

    def list_model_years(self) -> list[int]:
        """List the model years in the project."""
        return list(range(self.start_year, self.end_year + 1, self.step_year))


"""
    dataset_id: "",
    filepath: "",
    projection_slice: "energy_by_sector|evs|heat_pumps",
    # valid dataset_types depend on chosen projection_slice
    dataset_type: "energy_by_sector|energy_intensity_by_sector|energy_intensity_regression_by_sector|population|gdp|...",
    # data that might go here, or in project_user_config, or in a separate "submit-to-project" step:
    # dataset requirements (e.g., to which sector(s) are these data applicable?)
    # mappings
    # ways to fill in missing data
    # in which scenario(s) to use these data

default datasets:
- GDP
- HDI
- energy intensity regressions
- population projections

When we generate the project config, the base dimensions will be the union of dimensions
in these datasets.

Regarding base dimensions:
- When we create the project, allow the user to specify dimensions from a library (2020 census counties).
- When we create a dataset, allow the user to specify which dimensions will become project base dimensions?
"""
