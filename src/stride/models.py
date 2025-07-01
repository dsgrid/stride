from enum import StrEnum

from pydantic import field_validator

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
    path: str | None = None
    dataset_type: DatasetType
    projection_slice: ProjectionSliceType | None = None  # TODO
    time_type: TimeDimensionType | None = None
    time_columns: list[str] = []
    dimension_columns: dict[str, DimensionType] = {}
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


class ProjectConfig(DSGBaseModel):
    """Defines a Stride project."""

    project_id: str
    creator: str
    description: str
    country: str
    start_year: int
    end_year: int
    datasets: list[DatasetConfig]


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
