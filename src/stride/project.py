from collections import defaultdict
import os
import shutil
import subprocess
from pathlib import Path
from typing import Self

from chronify.exceptions import InvalidParameter
import duckdb
from chronify.utils.path_utils import check_overwrite
from dsgrid.utils.files import dump_json_file
from duckdb import DuckDBPyConnection, DuckDBPyRelation
from loguru import logger

import stride
from stride.default_datasets import create_test_datasets
from stride.default_project import create_dsgrid_project
from stride.dsgrid_integration import deploy_to_dsgrid_registry, make_mapped_datasets
from stride.io import create_table_from_file, export_table
from stride.models import (
    IntermediateTableOverride,
    IntermediateTableOverrides,
    ProjectConfig,
)

CONFIG_FILE = "project.json5"
TABLE_OVERRIDES_FILE = "table_overrides.json5"
DATABASE_FILE = "data.duckdb"
REGISTRY_DATA_DIR = "registry_data"
DBT_DIR = "dbt"


class Project:
    """Manages a Stride project."""

    def __init__(
        self,
        config: ProjectConfig,
        project_path: Path,
        table_overrides: IntermediateTableOverrides | None = None,
    ) -> None:
        self._config = config
        self._path = project_path
        self._con = self._connect()
        self._table_overrides = table_overrides or IntermediateTableOverrides()

    def _connect(self) -> DuckDBPyConnection:
        return duckdb.connect(self._path / REGISTRY_DATA_DIR / DATABASE_FILE)

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
        for scenario in config.scenarios:
            make_mapped_datasets(project.con, project_path, config.project_id, scenario.name)
        project.persist()
        project.copy_dbt_template()
        project.compute_energy_projection()
        return project

    @classmethod
    def load(cls, project_path: Path | str) -> Self:
        """Load a project from a serialized directory."""
        path = Path(project_path)
        config_file = path / CONFIG_FILE
        db_file = path / "registry_data" / DATABASE_FILE
        if not config_file.exists() or not db_file.exists():
            msg = f"{path} does not contain a Stride project"
            raise InvalidParameter(msg)
        config = ProjectConfig.from_file(config_file)
        return cls(config, path)

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

    @property
    def path(self) -> Path:
        """Return the project path."""
        return self._path

    def override_intermediate_table(
        self, scenario_name: str, table_name: str, filename: Path
    ) -> None:
        """Override an intermediate table for a scenario."""
        self._check_scenario_present(scenario_name)
        self._check_intermediate_table_present(scenario_name, table_name)
        existing_full_name = f"{scenario_name}.{table_name}"
        override_name = f"{table_name}_override_table"
        override_full_name = f"{scenario_name}.{override_name}"
        create_table_from_file(self._con, override_full_name, filename, replace=True)  # noqa: F841
        new_schema = self._get_table_schema_types(override_full_name)
        new_schema.sort(key=lambda x: x["column_name"])
        existing_schema = self._get_table_schema_types(existing_full_name)
        existing_schema.sort(key=lambda x: x["column_name"])
        if new_schema != existing_schema:
            self._con.sql(f"DROP TABLE {override_full_name}")
            msg = (
                f"The schema for the override table, {new_schema}, "
                f"must match the existing schema, {existing_schema}"
            )
            raise InvalidParameter(msg)
        override_file = self._path / DBT_DIR / "models" / f"{table_name}_override.sql"
        override_file.write_text(f"SELECT * FROM {override_full_name}")
        self._table_overrides.tables.append(
            IntermediateTableOverride(scenario=scenario_name, table_name=table_name)
        )
        logger.info("Added override table {} to scenario {}", table_name, scenario_name)
        # TODO: we don't need to rebuild all scenarios, but dbt caching should help.
        # If the user has many tables to add, we could add them in a batch and rebuild once.
        self.compute_energy_projection()
        self.persist()

    def copy_dbt_template(self) -> None:
        """Copy the dbt template for all scenarios."""
        stride_base_dir = Path(next(iter(stride.__path__)))
        dbt_dir = self._path / DBT_DIR
        shutil.copytree(stride_base_dir / DBT_DIR, dbt_dir)
        src_file = stride_base_dir / DBT_DIR / "energy_projection_scenario_placeholder.sql"
        dst_file = self._path / DBT_DIR / "models" / "energy_projection.sql"
        shutil.copyfile(src_file, dst_file)

    def export_intermediate_table(
        self, scenario_name: str, table_name: str, filename: Path, overwrite: bool = False
    ) -> None:
        """Export the specified intermediate table to filename. Supports CSV and Parquet, inferred
        from the filename's suffix.
        """
        check_overwrite(filename, overwrite)
        self._check_intermediate_table_present(scenario_name, table_name)
        full_name = f"{scenario_name}.{table_name}"
        export_table(self._con, full_name, filename)
        logger.info("Exported scenario={} table={} to {}", scenario_name, table_name, filename)

    def has_table(self, name: str, schema: str = "main") -> bool:
        """Return True if the table name is in the specified schema."""
        return name in self.list_tables(schema=schema)

    def list_scenario_names(self) -> list[str]:
        """Return a list of scenario names in the project."""
        return [x.name for x in self._config.scenarios]

    def list_tables(self, schema: str = "main") -> list[str]:
        """List all tables stored in the database in the specified schema."""
        result = self._con.execute(
            f"""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = '{schema}'
        """
        ).fetchall()
        return [x[0] for x in result]

    def list_intermediate_tables(self, scenario: str) -> list[str]:
        """List all intermediate tables stored in the database the scenario."""
        return self.list_tables(schema=scenario)

    def persist(self) -> None:
        """Persist the project config to the project directory."""
        dump_json_file(self._config.model_dump(mode="json"), self._path / CONFIG_FILE, indent=2)
        dump_json_file(
            self._table_overrides.model_dump(mode="json"),
            self._path / TABLE_OVERRIDES_FILE,
            indent=2,
        )

    def compute_energy_projection(self) -> None:
        """Compute the energy projection dataset from all scenarios."""
        table_overrides = self._get_table_overrides()
        orig = os.getcwd()
        model_years = ",".join((str(x) for x in self._config.list_model_years()))
        for i, scenario in enumerate(self._config.scenarios):
            overrides = table_overrides.get(scenario.name, [])
            override_strings = [f'"{x}_override": "{x}_override"' for x in overrides]
            override_str = ", " + ", ".join(override_strings) if override_strings else ""
            vars_string = (
                f'{{"scenario": "{scenario.name}", '
                f'"country": "{self._config.country}", '
                f'"model_years": "({model_years})"'
                f"{override_str}}}"
            )
            cmd = ["dbt", "build", "--vars", vars_string]
            self._con.close()
            try:
                os.chdir(self._path / DBT_DIR)
                logger.info("Build scenario={} dbt models with '{}'", scenario.name, " ".join(cmd))
                subprocess.run(cmd, check=True)
            finally:
                os.chdir(orig)
                self._con = self._connect()

            columns = "timestamp, model_year, scenario, sector, geography, metric, value"
            if i == 0:
                query = f"""
                    CREATE OR REPLACE TABLE energy_projection
                    AS
                    SELECT {columns}
                    FROM {scenario.name}.energy_projection
                """
                self._con.sql(query)
            else:
                query = f"""
                    INSERT INTO energy_projection
                    SELECT {columns}
                    FROM {scenario.name}.energy_projection
                """
                self._con.sql(query)
            logger.info(
                "Added energy_projection from scenario {} to energy_projection.",
                scenario.name,
            )
        self._con.commit()

    def get_energy_projection(self, scenario: str | None = None) -> DuckDBPyRelation:
        """Return the energy projection table, optionally for a scenario.

        Parameters
        ----------
        scenario
            By default, return a table with all scenarios. Otherwise, filter on one scenario.

        Returns
        -------
        DuckDBPyRelation
            Relation containing the data.
        """
        if scenario is None:
            return self._con.sql("SELECT * FROM energy_projection")
        return self._con.sql(
            f"SELECT * FROM {scenario}.energy_projection WHERE scenario = ?", params=(scenario,)
        )

    def show_dataset(self, dataset_id: str, scenario: str = "baseline", limit: int = 20) -> None:
        """Return a list of scenario names in the project."""
        table = f"dsgrid_data.{scenario}__{dataset_id}__1_0_0"
        print(self._con.sql(f"SELECT * FROM {table} LIMIT {limit}"))

    def _get_table_overrides(self) -> dict[str, list[str]]:
        overrides: dict[str, list[str]] = defaultdict(list)
        for override in self._table_overrides.tables:
            overrides[override.scenario].append(override.table_name)
        return overrides

    def _check_scenario_present(self, scenario_name: str) -> None:
        scenarios = self.list_scenario_names()
        if scenario_name not in scenarios:
            msg = f"{scenario_name=} is not stored in the project's scenarios"
            raise InvalidParameter(msg)

    def _check_intermediate_table_present(self, scenario_name: str, table_name: str) -> None:
        self._check_scenario_present(scenario_name)
        if table_name not in self.list_intermediate_tables(scenario_name):
            msg = f"{table_name=} is not an intermediate table in scenario={scenario_name}"
            raise InvalidParameter(msg)

    def _get_table_schema_types(self, table_name: str) -> list[dict[str, str]]:
        """Return the types of each column in the table."""
        return [
            {"column_name": x[0], "column_type": x[1]}
            for x in self._con.sql(f"DESCRIBE {table_name}").fetchall()
        ]
