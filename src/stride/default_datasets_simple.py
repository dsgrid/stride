from pathlib import Path

from dsgrid.dimension.base_models import DimensionType

import stride
from stride.models import DatasetConfig


def create_default_test_datasets(metrics_map: dict[str, str]) -> list[DatasetConfig]:
    """Create a list of default stride datasets for tests."""
    data_path = Path(next(iter(stride.__path__))).parents[1] / "tests" / "data"
    return [
        DatasetConfig(
            dataset_id="energy_intensity",
            path=data_path / "energy_intensity.csv",
            metric_class="EnergyIntensityRegression",
            metric_dimension_name=metrics_map["EnergyIntensityRegression"],
            dimension_columns={
                "country": DimensionType.GEOGRAPHY,
                "metric": DimensionType.METRIC,
                "sector": DimensionType.SECTOR,
            },
        ),
        DatasetConfig(
            dataset_id="gdp",
            path=data_path / "gdp.csv",
            metric_class="Stock",
            metric_dimension_name=metrics_map["Stock"],
            dimension_columns={
                "country": DimensionType.GEOGRAPHY,
                "year": DimensionType.MODEL_YEAR,
            },
        ),
        DatasetConfig(
            dataset_id="hdi",
            path=data_path / "hdi.csv",
            metric_class="FractionalIndex",
            metric_dimension_name=metrics_map["FractionalIndex"],
            dimension_columns={
                "country": DimensionType.GEOGRAPHY,
                "year": DimensionType.MODEL_YEAR,
            },
        ),
        DatasetConfig(
            dataset_id="population",
            path=data_path / "population.csv",
            metric_class="Population",
            metric_dimension_name=metrics_map["Population"],
            dimension_columns={
                "country": DimensionType.GEOGRAPHY,
                "year": DimensionType.MODEL_YEAR,
            },
        ),
        DatasetConfig(
            dataset_id="load_shapes",
            path=data_path / "load_shapes.csv",
            metric_class="EnergyEndUse",
            metric_dimension_name=metrics_map["EnergyEndUse"],
            dimension_columns={
                "country": DimensionType.GEOGRAPHY,
                "year": DimensionType.MODEL_YEAR,
                "sector": DimensionType.SECTOR,
                "enduse": DimensionType.METRIC,
            },
        ),
    ]
