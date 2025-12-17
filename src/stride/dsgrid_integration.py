import json
import tempfile
from pathlib import Path

from dsgrid.query.models import DimensionReferenceModel, make_dataset_query
from dsgrid.utils.files import load_json_file
import duckdb
from dsgrid.query.query_submitter import (
    DatasetQuerySubmitter,
)
from dsgrid.registry.bulk_register import bulk_register
from dsgrid.registry.common import DataStoreType, DatabaseConnection
from dsgrid.registry.registry_manager import RegistryManager
from loguru import logger


def deploy_to_dsgrid_registry(
    registry_path: Path,
    dataset_dir: Path,
) -> None:
    """Deploy the Stride project to a dsgrid registry."""
    registration_file = dataset_dir / "registration.json5"
    if not registration_file.exists():
        msg = f"Registration file not found: {registration_file}"
        raise FileNotFoundError(msg)

    mgr = create_dsgrid_registry(registry_path)
    bulk_register(
        mgr,
        registration_file,
        repo_base_dir=dataset_dir,
    )
    logger.info("Registered dsgrid project and datasets from {}", dataset_dir)


def create_dsgrid_registry(registry_path: Path) -> RegistryManager:
    """Create a dsgrid registry."""
    url = _registry_url(registry_path)
    data_dir = registry_path / "registry_data"
    scratch_dir = (registry_path / "__dsgrid_scratch__").resolve()
    conn = DatabaseConnection(url=url)
    return RegistryManager.create(
        conn,
        data_dir,
        data_store_type=DataStoreType.DUCKDB,
        overwrite=True,
        scratch_dir=scratch_dir,
    )


def make_mapped_datasets(
    con: duckdb.DuckDBPyConnection,
    base_path: Path,
    project_id: str,
    scenario: str,
) -> None:
    """Create mapped datasets from the dsgrid registry and data files."""
    url = _registry_url(base_path)
    mgr = RegistryManager.load(DatabaseConnection(url=url), use_remote_data=False)
    scratch_dir = Path(tempfile.gettempdir())
    project = mgr.project_manager.load_project(project_id)
    time_dimension = project.config.get_base_time_dimension()
    to_dimension_references = [
        DimensionReferenceModel(
            dimension_id=time_dimension.model.dimension_id,
            type=time_dimension.model.dimension_type,
            version=time_dimension.model.version,
        ),
    ]
    dataset_ids = [f"{scenario}__load_shapes"]
    output_dir = base_path / "dsgrid_query_output"
    submitter = DatasetQuerySubmitter(output_dir)
    for dataset_id in dataset_ids:
        query = make_dataset_query(
            name=dataset_id,
            dataset_id=dataset_id,
            to_dimension_references=to_dimension_references,
        )
        # This calls toPandas() because the duckdb connection inside dsgrid is
        # different than this one. We need to extract it and then add it through this connection.
        df = submitter.submit(  # noqa F841
            query,
            mgr,
            scratch_dir=scratch_dir,
            overwrite=True,
        ).toPandas()
        # TODO: this should go into the stride schema.
        # ... challenges with sources.yml
        # table_name = f"stride.{dataset_id}"
        table_name = f"dsgrid_data.{dataset_id}"
        con.sql(f"CREATE TABLE {table_name} AS SELECT * FROM df")
        logger.info("Created table {} from mapped dataset.", table_name)


def register_scenario_datasets(
    registry_path: Path,
    dataset_dir: Path,
    scenario: str,
    table_names: list[str],
) -> None:
    """Register datasets for a non-baseline scenario.

    For tables that are not overridden in a scenario, create dsgrid dataset
    registrations that reference the baseline dataset configuration files.

    Parameters
    ----------
    registry_path : Path
        Path to the project/registry
    dataset_dir : Path
        Path to the data directory (e.g., ~/.stride/data/global-test)
    scenario : str
        Name of the scenario to create datasets for
    table_names : list[str]
        Names of tables to create datasets for
    """
    url = _registry_url(registry_path)
    mgr = RegistryManager.load(DatabaseConnection(url=url), use_remote_data=False)

    # Load the registration file to find dataset config files
    registration_file = dataset_dir / "registration.json5"
    registration_data = load_json_file(registration_file)

    # Build a mapping of dataset_id -> config_file path
    dataset_config_files: dict[str, Path] = {}
    for dataset_entry in registration_data.get("datasets", []):
        dataset_id = dataset_entry.get("dataset_id")
        config_file = dataset_entry.get("config_file")
        if dataset_id and config_file:
            dataset_config_files[dataset_id] = dataset_dir / config_file

    for table_name in table_names:
        baseline_dataset_id = f"baseline__{table_name}"
        config_file_path = dataset_config_files.get(baseline_dataset_id)
        if config_file_path is None or not config_file_path.exists():
            logger.debug(
                "Config file for {} not found, skipping alias creation",
                baseline_dataset_id,
            )
            continue

        # Load the original config file
        dataset_config = load_json_file(config_file_path)

        # Update the dataset_id for the new scenario
        new_dataset_id = f"{scenario}__{table_name}"
        dataset_config["dataset_id"] = new_dataset_id

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json") as tmp_file:
            json.dump(dataset_config, tmp_file, indent=2)
            tmp_path = Path(tmp_file.name)
            mgr.dataset_manager.register(tmp_path)
            logger.info("Registered scenario dataset {}", new_dataset_id)


def _registry_url(registry_path: Path) -> str:
    return f"sqlite:///{registry_path}/registry.db"
