import os
import shutil
import subprocess
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Self

import duckdb
from chronify.exceptions import InvalidOperation, InvalidParameter
from chronify.utils.path_utils import check_overwrite
from dsgrid.utils.files import dump_json_file
from duckdb import DuckDBPyConnection, DuckDBPyRelation
from loguru import logger

import stride
from stride.db_interface import make_dsgrid_data_table_name
from stride.default_datasets import create_test_datasets
from stride.default_project import create_dsgrid_project
from stride.dsgrid_integration import deploy_to_dsgrid_registry, make_mapped_datasets
from stride.io import create_table_from_file, export_table
from stride.models import (
    CalculatedTableOverride,
    ProjectConfig,
    Scenario,
)

CONFIG_FILE = "project.json5"
DATABASE_FILE = "data.duckdb"
REGISTRY_DATA_DIR = "registry_data"
DBT_DIR = "dbt"


class Project:
    """Manages a Stride project."""

    def __init__(
        self,
        config: ProjectConfig,
        project_path: Path,
        **connection_kwargs: Any,
    ) -> None:
        self._config = config
        self._path = project_path
        self._con = self._connect(**connection_kwargs)

    def _connect(self, **connection_kwargs: Any) -> DuckDBPyConnection:
        return duckdb.connect(self._path / REGISTRY_DATA_DIR / DATABASE_FILE, **connection_kwargs)

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: Any, **kwargs: Any) -> None:
        if hasattr(self, "_con") and self._con is not None:
            self._con.close()

    @classmethod
    def create(
        cls, config_file: Path | str, base_dir: Path = Path(), overwrite: bool = False
    ) -> Self:
        """Create a project from a config file.

        Parameters
        ----------
        config_file
            Defines the project inputs.
        base_dir
            Base dir in which to create the project directory, defaults to the current directory.
            The project directory will be `base_dir / project_id`.
        overwrite
            Set to True to overwrite the project directory if it already exists.

        Examples
        --------
        >>> Project.create("my_project.json5")
        """
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
            for dataset in project.list_datasets():
                # There is no reason to keep the user's dataset paths.
                setattr(scenario, dataset, None)
        project.persist()
        project.copy_dbt_template()
        project.compute_energy_projection(use_table_overrides=False)
        if config.calculated_table_overrides:
            overrides = config.calculated_table_overrides
            # The override method will append to this list after a successful operation,
            # so we need to reassign it first.
            config.calculated_table_overrides = []
            project.override_calculated_tables(overrides)

        return project

    @classmethod
    def load(cls, project_path: Path | str, **connection_kwargs: Any) -> Self:
        """Load a project from a serialized directory.

        Parameters
        ----------
        project_path
            Directory containing an existing project.
        connection_kwargs
            Keyword arguments to be forwarded to the DuckDB connect call.
            Pass read_only=True if you will not be mutating the database
            so that multiple stride processes can access the database simultaneously.

        Examples
        --------
        >>> from stride import Project
        >>> with Project.load("my_project_path", read_only=True) as project:
            project.list_scenario_names()
        """
        path = Path(project_path)
        config_file = path / CONFIG_FILE
        db_file = path / "registry_data" / DATABASE_FILE
        if not config_file.exists() or not db_file.exists():
            msg = f"{path} does not contain a Stride project"
            raise InvalidParameter(msg)
        config = ProjectConfig.from_file(config_file)
        return cls(config, path, **connection_kwargs)

    def close(self) -> None:
        """Close the connection to the database."""
        self._con.close()

    @property
    def con(self) -> DuckDBPyConnection:
        """Return the connection to the database."""
        return self._con

    @property
    def config(self) -> ProjectConfig:
        """Return the project configuration."""
        return self._config

    @property
    def path(self) -> Path:
        """Return the project path."""
        return self._path

    def override_calculated_tables(self, overrides: list[CalculatedTableOverride]) -> None:
        """Override one or more calculated tables."""
        for table in overrides:
            if table.filename is None:
                msg = f"The file_path for a calculated_table_override cannot be None: {table}."
                raise InvalidParameter(msg)
            if "_override" in table.table_name:
                msg = f"Overriding an override table is not supported: {table.table_name=}"
                raise InvalidOperation(msg)

        for table in overrides:
            assert table.filename is not None
            self._check_scenario_present(table.scenario)
            self._check_calculated_table_present(table.scenario, table.table_name)
            existing_full_name = f"{table.scenario}.{table.table_name}"
            override_name = f"{table.table_name}_override_table"
            override_full_name = f"{table.scenario}.{override_name}"
            dtypes = self._get_dtypes(Path(table.filename))
            create_table_from_file(
                self._con, override_full_name, table.filename, replace=True, dtypes=dtypes
            )  # noqa: F841
            self._check_schemas(override_full_name, existing_full_name)
            override_file = self._path / DBT_DIR / "models" / f"{table.table_name}_override.sql"
            override_file.write_text(f"SELECT * FROM {override_full_name}")
            self._config.calculated_table_overrides.append(
                CalculatedTableOverride(scenario=table.scenario, table_name=table.table_name)
            )
            logger.info("Added override table {} to scenario {}", table.table_name, table.scenario)

        # TODO: we don't need to rebuild all scenarios. Does dbt caching remove the need to worry?
        self.compute_energy_projection()
        self.persist()

    def remove_calculated_table_overrides(self, overrides: list[CalculatedTableOverride]) -> None:
        """Remove an overridden calculated table.

        Parameters
        ----------
        overrides
            Remove the specified overrides.

        Examples
        --------
        >>> project.remove_calculated_table_override(
        ...     [
        ...         CalculatedTableOverride(
        ...             scenario="baseline",
        ...             table_name="energy_projection_res_load_shapes",
        ...         )
        ...     ]
        ... )
        >>> project.remove_calculated_table_override(
        ...     [
        ...         CalculatedTableOverride(
        ...             scenario="baseline",
        ...             table_name="energy_projection_res_load_shapes_override",
        ...         )
        ...     ]
        ... )
        """
        cache: dict[int, dict[str, Any]] = {}
        for user_table in overrides:
            base_name, override_name = _get_base_and_override_names(user_table.table_name)
            override_full_name = f"{user_table.scenario}.{override_name}"
            self._check_scenario_present(user_table.scenario)
            self._check_calculated_table_present(user_table.scenario, override_name)
            index = None
            for i, config_table in enumerate(self._config.calculated_table_overrides):
                if (
                    config_table.scenario == user_table.scenario
                    and config_table.table_name == base_name
                ):
                    index = i
                    break
            if index is None:
                msg = f"Bug: did not find override for table name {user_table.scenario=} {base_name=}"
                raise Exception(msg)
            if index in cache:
                msg = f"{override_full_name} was provided multiple times"
                raise InvalidOperation(msg)
            cache[index] = {
                "base_name": base_name,
                "override_name": override_name,
                "override_full_name": override_full_name,
            }

        indexes = reversed(cache.keys())
        for index in indexes:
            item = cache[index]
            base_name = item["base_name"]
            override_name = item["override_name"]
            override_full_name = item["override_full_name"]
            self._con.sql(f"DROP VIEW {override_full_name}")
            self._config.calculated_table_overrides.pop(index)
            override_file = self._path / DBT_DIR / "models" / f"{override_name}.sql"
            override_file.unlink()
            logger.info("Removed override table {}", override_full_name)

        # TODO: we don't need to rebuild all scenarios. Does dbt caching remove the need to worry?
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

    def export_calculated_table(
        self, scenario_name: str, table_name: str, filename: Path, overwrite: bool = False
    ) -> None:
        """Export the specified calculated table to filename. Supports CSV and Parquet, inferred
        from the filename's suffix.
        """
        check_overwrite(filename, overwrite)
        self._check_calculated_table_present(scenario_name, table_name)
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

    def list_calculated_tables(self) -> list[str]:
        """List all calculated tables stored in the database. They apply to each scenario."""
        dbt_dir = self._path / DBT_DIR / "models"
        return sorted([x.stem for x in dbt_dir.glob("*.sql")])

    @staticmethod
    def list_datasets() -> list[str]:
        """List the datasets available in any project."""
        return [x for x in Scenario.model_fields if x != "name"]

    def persist(self) -> None:
        """Persist the project config to the project directory."""
        dump_json_file(self._config.model_dump(mode="json"), self._path / CONFIG_FILE, indent=2)

    def compute_energy_projection(self, use_table_overrides: bool = True) -> None:
        """Compute the energy projection dataset for all scenarios.

        This operation overwrites all tables and views in the database.

        Parameters
        ----------
        use_table_overrides
            If True, use compute results based on the table overrides specified in the project
            config.
        """
        orig = os.getcwd()
        model_years = ",".join((str(x) for x in self._config.list_model_years()))
        table_overrides = self.get_table_overrides() if use_table_overrides else {}
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
            # TODO: May want to run `build` instead of `run` if we add dbt tests.
            cmd = ["dbt", "run", "--vars", vars_string]
            self._con.close()
            try:
                os.chdir(self._path / DBT_DIR)
                logger.info("Run scenario={} dbt models with '{}'", scenario.name, " ".join(cmd))
                start = time.time()
                subprocess.run(cmd, check=True)
                duration = time.time() - start
                logger.debug("Time to run dbt for scenario={}: {} s", scenario.name, duration)
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
        table = make_dsgrid_data_table_name(scenario, dataset_id)
        print(self._con.sql(f"SELECT * FROM {table} LIMIT {limit}"))

    def get_table_overrides(self) -> dict[str, list[str]]:
        """Return a dictionary of tables being overridden for each scenario."""
        overrides: dict[str, list[str]] = defaultdict(list)
        for override in self._config.calculated_table_overrides:
            overrides[override.scenario].append(override.table_name)
        return overrides

    def _check_schemas(self, override_full_name: str, existing_full_name: str) -> None:
        new_schema = self._get_table_schema_types(override_full_name)
        new_schema.sort(key=lambda x: x["column_name"])
        existing_schema = self._get_table_schema_types(existing_full_name)
        existing_schema.sort(key=lambda x: x["column_name"])
        if new_schema != existing_schema:
            self._con.sql(f"DROP TABLE {override_full_name}")
            if len(new_schema) != len(existing_schema):
                override_columns = [x["column_name"] for x in new_schema]
                existing_columns = [x["column_name"] for x in existing_schema]
                msg = (
                    "The columns in the override table do not match the existing table. \n"
                    f"{override_columns=} {existing_columns=}"
                )
                raise InvalidParameter(msg)
            else:
                for i in range(len(new_schema)):
                    if new_schema[i] != existing_schema[i]:
                        msg = (
                            f"The schema for the override table, {new_schema[i]}, "
                            f"must match the existing schema, {existing_schema[i]}"
                        )
                        raise InvalidParameter(msg)
            msg = "Bug: unexpectedly did not find a mismatch {new_schema=} {existing_schema=}"
            raise Exception(msg)

    def _check_scenario_present(self, scenario_name: str) -> None:
        scenarios = self.list_scenario_names()
        if scenario_name not in scenarios:
            msg = f"{scenario_name=} is not stored in the project's scenarios"
            raise InvalidParameter(msg)

    def _check_calculated_table_present(self, scenario_name: str, table_name: str) -> None:
        self._check_scenario_present(scenario_name)
        if table_name not in self.list_calculated_tables():
            msg = f"{table_name=} is not a calculated table in scenario={scenario_name}"
            raise InvalidParameter(msg)

    @staticmethod
    def _get_dtypes(filename: Path) -> dict[str, Any] | None:
        """Should only be used when we know it's safe."""
        dtypes: dict[str, str] | None = None
        if filename.suffix == ".csv":
            has_timestamp = False
            with open(filename, "r", encoding="utf-8") as f_in:
                for line in f_in:
                    if "timestamp" in line:
                        has_timestamp = True
                    break
            if has_timestamp:
                dtypes = {"timestamp": "timestamp with time zone"}
        return dtypes

    def _get_table_schema_types(self, table_name: str) -> list[dict[str, str]]:
        """Return the types of each column in the table."""
        return [
            {"column_name": x[0], "column_type": x[1]}
            for x in self._con.sql(f"DESCRIBE {table_name}").fetchall()
        ]


def _get_base_and_override_names(table_name: str) -> tuple[str, str]:
    if table_name.endswith("_override"):
        base_name = table_name.replace("_override", "", 1)
        if "override" in base_name:
            msg = f"'override' is still present in '{base_name}'. {table_name=} is unexpected"
            raise InvalidParameter(msg)
        override_name = table_name
    else:
        base_name = table_name
        override_name = f"{table_name}_override"
    return base_name, override_name
