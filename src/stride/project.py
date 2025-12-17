import importlib.resources
import os
import shutil
import subprocess
import sys
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

from stride.dataset_download import get_default_data_directory
from stride.db_interface import make_dsgrid_data_table_name
from stride.dsgrid_integration import (
    deploy_to_dsgrid_registry,
    make_mapped_datasets,
    register_scenario_datasets,
)
from stride.io import create_table_from_file, export_table
from stride.models import (
    CalculatedTableOverride,
    ProjectConfig,
    Scenario,
)
from stride.ui.palette import ColorPalette

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
        self._palette: ColorPalette | None = None

    def _connect(self, **connection_kwargs: Any) -> DuckDBPyConnection:
        return duckdb.connect(self._path / REGISTRY_DATA_DIR / DATABASE_FILE, **connection_kwargs)

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: Any, **kwargs: Any) -> None:
        if hasattr(self, "_con") and self._con is not None:
            self._con.close()

    @classmethod
    def create(
        cls,
        config_file: Path | str,
        base_dir: Path = Path(),
        overwrite: bool = False,
        use_test_data: bool = False,
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
        use_test_data
            If True, use the smaller test dataset (global-test).
            If False (default), use the full dataset (global).

        Examples
        --------
        >>> Project.create("my_project.json5")
        """
        config = ProjectConfig.from_file(config_file)
        project_path = base_dir / config.project_id
        check_overwrite(project_path, overwrite)
        project_path.mkdir()

        dataset_dir = cls._get_dataset_dir(use_test_data)
        deploy_to_dsgrid_registry(project_path, dataset_dir)

        unchanged_tables_by_scenario = cls._register_scenario_datasets(
            config, project_path, dataset_dir
        )

        project = cls(config, project_path)
        project.con.sql("CREATE SCHEMA stride")
        project._clear_scenario_dataset_paths()
        for scenario in config.scenarios:
            make_mapped_datasets(
                project.con, dataset_dir, project.path, project.config.project_id, scenario.name
            )

        project.persist()
        project.copy_dbt_template()
        project._create_views_for_unchanged_tables(unchanged_tables_by_scenario)
        project.compute_energy_projection(use_table_overrides=False)
        project._apply_calculated_table_overrides()

        # Populate the color palette with all metrics from the database
        project.populate_palette_metrics()
        project.save_palette()

        # Close the connection and reload to return a clean project instance
        # This ensures the returned project has a fresh connection with default settings
        project.close()
        return cls.load(project_path)

    @classmethod
    def _get_dataset_dir(cls, use_test_data: bool) -> Path:
        """Get and validate the dataset directory."""
        dataset_name = "global-test" if use_test_data else "global"
        dataset_dir = get_default_data_directory() / dataset_name
        if not dataset_dir.exists():
            msg = (
                f"Dataset directory not found: {dataset_dir}. "
                f"Please download it first using: stride datasets download {dataset_name}"
            )
            raise InvalidParameter(msg)
        return dataset_dir

    @classmethod
    def _register_scenario_datasets(
        cls,
        config: ProjectConfig,
        project_path: Path,
        dataset_dir: Path,
    ) -> dict[str, list[str]]:
        """Register alias datasets with dsgrid for non-baseline scenarios.

        Returns a mapping of scenario name to list of unchanged table names.
        """
        datasets = cls.list_datasets()
        unchanged_tables_by_scenario: dict[str, list[str]] = {}
        for scenario in config.scenarios:
            if scenario.name != "baseline":
                unchanged_tables_by_scenario[scenario.name] = [
                    d for d in datasets if getattr(scenario, d) is None
                ]
                new_tables = [d for d in datasets if getattr(scenario, d) is not None]
                if new_tables:
                    register_scenario_datasets(
                        project_path, dataset_dir, scenario.name, new_tables
                    )
        return unchanged_tables_by_scenario

    def _clear_scenario_dataset_paths(self) -> None:
        """Clear dataset paths from scenario configs (no longer needed after loading)."""
        for scenario in self._config.scenarios:
            for dataset in self.list_datasets():
                setattr(scenario, dataset, None)

    def _create_views_for_unchanged_tables(
        self, unchanged_tables_by_scenario: dict[str, list[str]]
    ) -> None:
        """Create views for unchanged tables in non-baseline scenarios."""
        for scenario_name, unchanged_tables in unchanged_tables_by_scenario.items():
            if unchanged_tables:
                self._create_baseline_views(scenario_name, unchanged_tables)

    def _apply_calculated_table_overrides(self) -> None:
        """Apply any calculated table overrides from the config."""
        if self._config.calculated_table_overrides:
            overrides = self._config.calculated_table_overrides
            # The override method will append to this list after a successful operation,
            # so we need to reassign it first.
            self._config.calculated_table_overrides = []
            self.override_calculated_tables(overrides)

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

    @property
    def palette(self) -> ColorPalette:
        """Get or create the color palette for this project.

        The palette is automatically populated with:
        - Scenarios from the project config
        - Model years from start_year, end_year, step_year
        - Metrics are populated during project creation

        To refresh metrics after project updates, call:
        >>> project.populate_palette_metrics()
        >>> project.save_palette()
        """
        if self._palette is None:
            self._palette = ColorPalette(self._config.color_palette)
            self._auto_populate_palette()
        return self._palette

    def _auto_populate_palette(self) -> None:
        """Auto-populate palette with scenarios and model_years from config if not already present."""
        if self._palette is None:
            return

        # Auto-populate scenarios from config
        scenario_names = [scenario.name for scenario in self._config.scenarios]
        for name in scenario_names:
            if name not in self._palette.scenarios:
                self._palette.update(name, category="scenarios")

        # Auto-populate model_years from config
        model_years = self._config.list_model_years()
        for year in model_years:
            year_str = str(year)
            if year_str not in self._palette.model_years:
                self._palette.update(year_str, category="model_years")

    def populate_palette_metrics(self) -> None:
        """Populate the palette with all metrics (sectors and end uses) from the database.

        This method queries the database for unique sectors and end uses and adds them
        to the metrics category of the palette. It's called automatically during project
        creation, but can be called manually to refresh the palette after updates.

        Examples
        --------
        >>> project = Project.load("my_project")
        >>> project.populate_palette_metrics()
        >>> project.save_palette()
        """
        from stride.api import APIClient

        if self._palette is None:
            # Initialize palette first
            _ = self.palette

        api_client = APIClient(self)

        # Get all unique sectors and end uses from the database
        sectors = api_client.get_unique_sectors()
        end_uses = api_client.get_unique_end_uses()

        # Add sectors to metrics category
        for sector in sectors:
            if self._palette is not None and sector not in self._palette.metrics:
                self._palette.update(sector, category="metrics")

        # Add end uses to metrics category
        for end_use in end_uses:
            if self._palette is not None and end_use not in self._palette.metrics:
                self._palette.update(end_use, category="metrics")

    def refresh_palette_colors(self) -> None:
        """Refresh all palette colors to use the correct themes for each category.

        This is useful for fixing palettes that may have incorrect color assignments
        (e.g., metrics using model year colors). It reassigns colors while preserving
        the labels in each category.

        Examples
        --------
        >>> project = Project.load("my_project")
        >>> project.refresh_palette_colors()
        >>> project.save_palette()
        """
        if self._palette is None:
            # Initialize palette first
            _ = self.palette

        # Refresh colors for each category using the correct theme
        if self._palette is not None:
            self._palette.refresh_category_colors("scenarios")
            self._palette.refresh_category_colors("model_years")
            self._palette.refresh_category_colors("metrics")

    def save_palette(self) -> None:
        """Save the current palette state back to the project conig file."""
        if self._palette is not None:
            self._config.color_palette = self._palette.to_dict()
            config_path = self._path / "project.json5"
            config_path.write_text(self._config.model_dump_json(indent=2))

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
        dbt_dir = self._path / DBT_DIR
        dbt_resource = importlib.resources.files("stride").joinpath(DBT_DIR)

        with importlib.resources.as_file(dbt_resource) as dbt_src:
            shutil.copytree(dbt_src, dbt_dir)

        src_file = dbt_dir / "energy_projection_scenario_placeholder.sql"
        dst_file = dbt_dir / "models" / "energy_projection.sql"
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

    def show_calculated_table(self, scenario_name: str, table_name: str, limit: int = 20) -> None:
        """Print a limited number of rows of the table to the console."""
        self._check_calculated_table_present(scenario_name, table_name)
        full_name = f"{scenario_name}.{table_name}"
        self._show_table(full_name, limit=limit)

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
                f'"model_years": "({model_years})", '
                f'"weather_year": {self._config.weather_year}, '
                f'"heating_threshold": {self._config.model_parameters.heating_threshold}, '
                f'"cooling_threshold": {self._config.model_parameters.cooling_threshold}'
                f"{override_str}}}"
            )
            # TODO: May want to run `build` instead of `run` if we add dbt tests.
            # Use dbt from the same environment as the running Python interpreter
            dbt_executable = Path(sys.executable).parent / "dbt"
            cmd = [str(dbt_executable), "run", "--vars", vars_string]
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

    def export_energy_projection(
        self, filename: Path = Path("energy_projection.csv"), overwrite: bool = False
    ) -> None:
        """Export the energy projection table to a file.

        Parameters
        ----------
        filename
            Filename to create. Supports .csv and .parquet.
        overwrite
            If True, overwrite the file if it already exists.

        Examples
        --------
        >>> project.export_energy_projection()
        INFO: Exported the energy projection table to energy_projection.csv
        """
        # FUTURE: users may want filters. Would need to determine how to accept the parameters.
        # Might be easier to let them create their own SQL query.
        # CLI users may still want something.
        check_overwrite(filename, overwrite)
        export_table(self._con, "energy_projection", filename)
        logger.info("Exported the energy projection table to {}", filename)

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

    def show_dataset(self, scenario: str, dataset_id: str, limit: int = 20) -> None:
        """Print a limited number of rows of the dataset to the console."""
        table = make_dsgrid_data_table_name(scenario, dataset_id)
        self._show_table(table, limit=limit)

    def _show_table(self, table: str, limit: int = 20) -> None:
        rel = self._con.sql(f"SELECT * FROM {table} LIMIT ?", params=(limit,))
        # DuckDB doesn't seem to provide a way to change the number of rows displayed.
        # If this is an issue, we could redirect to Pandas and customize the output.
        print(rel)

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

    def _create_baseline_views(self, scenario: str, table_names: list[str]) -> None:
        """Create views in a scenario schema that point to baseline tables.

        Parameters
        ----------
        scenario : str
            Name of the scenario
        table_names : list[str]
            Names of tables to create views for
        """
        scenario_config = next((s for s in self._config.scenarios if s.name == scenario), None)
        if scenario_config is None:
            return

        self._con.sql(f"CREATE SCHEMA IF NOT EXISTS {scenario}")

        for table_name in table_names:
            baseline_tables = self.list_tables(schema="dsgrid_data")
            existing_table_name = f"baseline__{table_name}__1_0_0"
            if existing_table_name not in baseline_tables:
                msg = f"Baseline table '{existing_table_name}' does not exist."
                raise InvalidParameter(msg)
            new_table_name = f"dsgrid_data.{scenario}__{table_name}__1_0_0"
            query = (
                f"CREATE OR REPLACE VIEW {new_table_name} AS "
                f"SELECT * FROM dsgrid_data.{existing_table_name}"
            )
            self._con.sql(query)
            logger.debug(
                "Created view {}.{} -> baseline.{}", scenario, new_table_name, existing_table_name
            )


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
