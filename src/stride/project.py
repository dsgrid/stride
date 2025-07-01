from pathlib import Path
from typing import Self

from chronify.exceptions import InvalidOperation, InvalidParameter
import duckdb
from chronify.utils.path_utils import check_overwrite
from dsgrid.utils.files import dump_data
from dsgrid.dimension.base_models import DimensionType
from dsgrid.dimension.time import TimeDimensionType
from dsgrid.config.dataset_config import DataSchemaType
from dsgrid.registry.common import DatabaseConnection
from dsgrid.registry.dataset_config_generator import generate_config_from_dataset
from dsgrid.registry.registry_manager import RegistryManager
from duckdb import DuckDBPyConnection
from loguru import logger

from stride.forecasts import compute_energy_projection
from stride.io import create_table_from_file
from stride.models import DatasetType, ProjectConfig, DatasetConfig


class Project:
    """Manages a Stride project."""

    CONFIG_FILE = "project.json5"
    ENERGY_PROJECTION = "energy_projection"
    DATABASE_FILE = "stride.duckdb"
    INPUT_CONFIGS_DIR = "input_configs"
    INPUT_DATASETS_DIR = "input_datasets"
    REGISTRY_FILE = "registry.db"
    REGISTRY_DATA_DIR = "registry_data"

    def __init__(self, config: ProjectConfig, project_path: Path, con: DuckDBPyConnection) -> None:
        self._con = con
        self._config = config
        self._path = project_path
        self._registry_db = self._path / self.REGISTRY_FILE

    @property
    def con(self) -> duckdb.DuckDBPyConnection:
        """Return the connection to the database."""
        return self._con

    @property
    def config(self) -> ProjectConfig:
        """Return the project configuration."""
        return self._config

    @classmethod
    def create(cls, config_file: Path, base_dir: Path = Path(), overwrite: bool = False) -> Self:
        """Create a project from a config file."""
        config = ProjectConfig.from_file(config_file)
        project_path = base_dir / config.project_id
        check_overwrite(project_path, overwrite)
        project_path.mkdir()
        db_file = project_path / cls.DATABASE_FILE
        con = duckdb.connect(str(db_file))
        project = cls(config, project_path, con)
        for dataset in config.datasets:
            if dataset.path is None:
                msg = f"{dataset.dataset_id} does not define a file path"
                raise InvalidOperation(msg)
            create_table_from_file(project.con, dataset.dataset_id, dataset.path)
            dataset.path = None
            # Henceforth, load from the db.

        project.compute_energy_projection()
        project.persist()
        return project

    @classmethod
    def load(cls, project_path: Path | str) -> Self:
        """Load a project from a serialized directory."""
        path = Path(project_path)
        config_file = path / cls.CONFIG_FILE
        db_file = path / cls.DATABASE_FILE
        if not config_file.exists() or not db_file.exists():
            msg = f"{path} does not contain a Stride project"
            raise InvalidParameter(msg)
        con = duckdb.connect(str(db_file))
        config = ProjectConfig.from_file(config_file)
        return cls(config, path, con)

    def persist(self) -> None:
        """Persist the project config to the project directory."""
        dump_data(self._config.model_dump(mode="json"), self._path / self.CONFIG_FILE, indent=2)

    def compute_energy_projection(self) -> None:
        """Compute the energy projection dataset and add it to the project."""
        for dataset in self._config.datasets:
            if dataset.dataset_id == self.ENERGY_PROJECTION:
                msg = f"{self.ENERGY_PROJECTION} is already created for project={self._config.project_id}"
                msg = InvalidOperation(msg)

        compute_energy_projection(
            self._con,
            "energy_intensity",
            "hdi",
            "gdp",
            "population",
            "hourly_profiles",
            "country",
            "country_1",
            table_name=self.ENERGY_PROJECTION,
        )
        ep_config = DatasetConfig(
            dataset_id=self.ENERGY_PROJECTION,
            dataset_type=DatasetType.ENERGY_BY_SECTOR,
            time_type=TimeDimensionType.INDEX,
            time_columns=["hour"],
            dimension_columns={
                "country": DimensionType.GEOGRAPHY,
                "sector": DimensionType.SECTOR,
                "year": DimensionType.MODEL_YEAR,
            },
        )
        self._config.datasets.append(ep_config)

    def deploy_to_dsgrid(self) -> None:
        """Deploy the Stride project to a dsgrid registry."""
        url = f"sqlite:///{self._path}/{self.REGISTRY_FILE}"
        data_dir = self._path / self.REGISTRY_DATA_DIR
        conn = DatabaseConnection(url=url)
        mgr = RegistryManager.create(conn, data_dir, overwrite=True)
        self._write_data_to_dsgrid_format()
        self._generate_dsgrid_dataset_configs(mgr)

    def _write_data_to_dsgrid_format(self):
        datasets_dir = self._path / self.INPUT_DATASETS_DIR
        datasets_dir.mkdir()
        dataset_paths: dict[str, Path] = {}
        datasets_to_skip = {"energy_intensity"}
        for dataset in self._config.datasets:
            if dataset.dataset_id in datasets_to_skip:
                logger.debug(
                    "Skipping {} dataset because it is not compatible with dsgrid.",
                    dataset.dataset_id,
                )
                continue
            dataset_path = datasets_dir / dataset.dataset_id
            dataset_path.mkdir()
            dataset_paths[dataset.dataset_id] = dataset_path

        for dataset in self.config.datasets:
            if dataset.dataset_id in datasets_to_skip:
                continue
            rel = self._con.table(dataset.dataset_id)
            expr: list[str] = dataset.time_columns + [dataset.value_column]
            needs_rename = False
            for column, dim_type in dataset.dimension_columns.items():
                if column != dim_type.value:
                    expr.append(f"{column} AS {dim_type.value}")
                    needs_rename = True
                else:
                    expr.append(column)
            if needs_rename:
                cols = ",".join(expr)
                rel = self._con.sql(f"SELECT {cols} FROM {rel.alias}")

            dpath = dataset_paths[dataset.dataset_id]
            rel.to_parquet(str(dpath / "table.parquet"))
            logger.info("Wrote dataset {} to dsgrid format at {}", dataset.dataset_id, dpath)

    def _generate_dsgrid_dataset_configs(self, mgr: RegistryManager) -> None:
        datasets_dir = self._path / self.INPUT_CONFIGS_DIR / "datasets"
        datasets_dir.mkdir(exist_ok=True, parents=True)
        for dataset in self.config.datasets:
            metric_type = (
                "EnergyEndUse" if dataset.dataset_id == self.ENERGY_PROJECTION else "Stock"
            )
            input_dataset_dir = self._path / self.INPUT_DATASETS_DIR / dataset.dataset_id
            if not input_dataset_dir.exists():
                # We may have skipped it above.
                continue
            included_dimensions = [x for x in dataset.dimension_columns.values()]
            if dataset.time_type is not None:
                included_dimensions.append(DimensionType.TIME)
            generate_config_from_dataset(
                mgr,
                dataset.dataset_id,
                input_dataset_dir,
                DataSchemaType.ONE_TABLE,
                metric_type,
                included_dimensions=included_dimensions,
                time_type=dataset.time_type,
                time_columns=set(dataset.time_columns),
                output_directory=datasets_dir,
                overwrite=True,
                # no_prompts=True,
            )
