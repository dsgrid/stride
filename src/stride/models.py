from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import Field, field_validator

from dsgrid.data_models import DSGBaseModel
from dsgrid.dimension.base_models import DimensionType
from dsgrid.dimension.time import TimeDimensionType


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


class DatasetConfig(DSGBaseModel):
    """Defines a Stride dataset."""

    dataset_id: str
    path: Path
    # dataset_type: DatasetType
    # projection_slice: ProjectionSliceType | None = None  # TODO
    metric_class: str
    metric_dimension_name: str
    time_type: TimeDimensionType | None = None
    time_columns: list[str] = []
    dimension_columns: dict[str, DimensionType] = {}
    trivial_dimensions: list[DimensionType] = []
    dimensions: list[dict[str, Any]]
    value_column: str = "value"

    @field_validator("dimension_columns")
    @classmethod
    def assign_dimensions(
        cls, columns: dict[str, DimensionType | str]
    ) -> dict[str, DimensionType]:
        final: dict[str, DimensionType] = {}
        for name, value in columns.items():
            if isinstance(value, DimensionType):
                final[name] = value
            else:
                final[name] = DimensionType(value)
        return final


class Scenario(DSGBaseModel):
    """Allows the user to add custom tables to compare against the defaults."""

    name: str = Field(description="Name of the scenario")
    energy_intensity: str | None = Field(
        default=None,
        description="Optional path to a user-provided energy intensity table",
    )
    gdp: str | None = Field(
        default=None,
        description="Optional path to a user-provided GDP table",
    )
    hdi: str | None = Field(
        default=None,
        description="Optional path to a user-provided HDI table",
    )
    load_shapes: str | None = Field(
        default=None,
        description="Optional path to a user-provided load shapes table",
    )
    population: str | None = Field(
        default=None,
        description="Optional path to a user-provided population table",
    )
    # TODO: bait, ev_share, vmt_per_capita


class ProjectConfig(DSGBaseModel):
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
        default=[Scenario(name="default")],
        description="Scenarios for the project. Users may add custom scenarios.",
    )

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
