import os
import shutil
import subprocess
from pathlib import Path
from typing import Literal, Self

from chronify.exceptions import InvalidParameter
import duckdb
from chronify.utils.path_utils import check_overwrite
from dsgrid.utils.files import dump_data
from duckdb import DuckDBPyConnection
from loguru import logger

import stride
from stride.default_datasets import create_test_datasets
from stride.default_project import create_dsgrid_project
from stride.dsgrid_integration import deploy_to_dsgrid_registry, make_mapped_datasets
from stride.models import ProjectConfig, Scenario

CONFIG_FILE = "project.json5"
DATABASE_FILE = "data.duckdb"
REGISTRY_DATA_DIR = "registry_data"
DBT_DIR = "dbt"


class Project:
    """Manages a Stride project."""

    def __init__(self, config: ProjectConfig, project_path: Path) -> None:
        self._config = config
        self._path = project_path
        self._con = self._connect()

    def _connect(self) -> DuckDBPyConnection:
        return duckdb.connect(self._path / REGISTRY_DATA_DIR / DATABASE_FILE)

    @property
    def con(self) -> DuckDBPyConnection:
        """Return the connection to the database."""
        return self._con

    @con.setter
    def con(self, con: DuckDBPyConnection) -> None:
        """Set the database connection."""
        self._con = con

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
        dsg_project = create_dsgrid_project(config)
        # TODO: this eventually needs a switch between test and real datasets.
        datasets = create_test_datasets(config, dsg_project)
        deploy_to_dsgrid_registry(project_path, dsg_project, datasets)
        project = cls(config, project_path)
        project.con.sql("CREATE SCHEMA stride")
        make_mapped_datasets(project.con, project_path, config.project_id)
        project.persist()
        dbt_dir = project_path / DBT_DIR
        stride_base_dir = Path(next(iter(stride.__path__)))
        shutil.copytree(stride_base_dir / DBT_DIR, dbt_dir)
        for scenario in config.scenarios:
            project.add_energy_projection_model(scenario.name)
            project.compute_energy_projection(scenario)
        return project

    @classmethod
    def load(cls, project_path: Path | str) -> Self:
        """Load a project from a serialized directory."""
        path = Path(project_path)
        config_file = path / CONFIG_FILE
        db_file = path / DATABASE_FILE
        if not config_file.exists() or not db_file.exists():
            msg = f"{path} does not contain a Stride project"
            raise InvalidParameter(msg)
        config = ProjectConfig.from_file(config_file)
        return cls(config, path)

    def add_energy_projection_model(self, scenario: str) -> None:
        stride_base_dir = Path(next(iter(stride.__path__)))
        src_file = stride_base_dir / DBT_DIR / "energy_projection.sql"
        dst_file = self._path / DBT_DIR / "models" / f"{scenario}__energy_projection.sql"
        shutil.copyfile(src_file, dst_file)

    def has_table(self, name: str, schema: Literal["stride", "dsgrid_data"] = "stride") -> bool:
        """Return True if the table name is in the specified schema."""
        return name in self.list_tables(schema=schema)

    def list_tables(self, schema: Literal["stride", "dsgrid_data"] = "stride") -> list[str]:
        """List all tables stored in the database in the specified schema."""
        result = self._con.execute(
            f"""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = '{schema}' AND table_type = 'BASE TABLE'
        """
        ).fetchall()
        return [x[0] for x in result]

    def persist(self) -> None:
        """Persist the project config to the project directory."""
        dump_data(self._config.model_dump(mode="json"), self._path / CONFIG_FILE, indent=2)

    def compute_energy_projection(self, scenario: Scenario) -> None:
        """Compute the energy projection dataset and add it to the project."""
        orig = os.getcwd()
        model_years = ",".join((str(x) for x in self._config.list_model_years()))
        for i, scenario in enumerate(self._config.scenarios):
            vars_string = f'{{scenario: "{scenario.name}", country: "{self._config.country}", model_years: "({model_years})"}}'
            cmd = [
                "dbt",
                "build",
                "--vars",
                vars_string,
            ]
            self._con.close()
            try:
                os.chdir(self._path / DBT_DIR)
                subprocess.run(cmd, check=True)
            finally:
                os.chdir(orig)
                self._con = self._connect()

            if i == 0:
                self._con.sql(
                    f"""
                    CREATE OR REPLACE TABLE energy_projection_total
                    AS
                    SELECT * FROM {scenario.name}__energy_projection
                """
                )
            else:
                self._con.sql(
                    """
                    INSERT INTO energy_projection_total
                    SELECT * from energy_projection
                """
                )
            logger.info(
                "Added energy_projection from scenario {} to energy_projection_total.",
                scenario.name,
            )
