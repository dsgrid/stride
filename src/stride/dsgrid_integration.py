import json
import tempfile
from getpass import getuser
from pathlib import Path

from chronify.exceptions import InvalidParameter
from dsgrid.config.mapping_tables import MappingTableModel
from dsgrid.config.registration_models import DimensionType
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
    dataset_dir: Path,
    base_path: Path,
    scenario: str,
) -> None:
    """Create mapped datasets from the dsgrid registry and data files."""
    url = _registry_url(base_path)
    mgr = RegistryManager.load(DatabaseConnection(url=url), use_remote_data=False)
    scratch_dir = Path(tempfile.gettempdir())
    dimension_mappings_file = dataset_dir / "dimension_mappings.json5"
    if not dimension_mappings_file.exists():
        return
    mappings = load_json_file(dimension_mappings_file).get("dimension_mappings")
    if not mappings:
        return

    output_dir = base_path / "dsgrid_query_output"
    query_submitter = DatasetQuerySubmitter(output_dir)
    mappings_dir = dimension_mappings_file.parent

    for mapping in mappings:
        _process_dataset_mapping(
            con=con,
            mapping=mapping,
            mappings_dir=mappings_dir,
            mgr=mgr,
            scenario=scenario,
            query_submitter=query_submitter,
            scratch_dir=scratch_dir,
        )


def _process_dataset_mapping(
    con: duckdb.DuckDBPyConnection,
    mapping: dict,
    mappings_dir: Path,
    mgr: RegistryManager,
    scenario: str,
    query_submitter: DatasetQuerySubmitter,
    scratch_dir: Path,
) -> None:
    """Process dimension mappings for a single dataset.

    Registers the mappings, queries the dataset with those mappings,
    and creates a table in DuckDB with the results.
    """
    mapping_file = mapping.get("dimension_mapping_file")
    if not mapping_file:
        return

    mapping_path = Path(mapping_file)
    if not mapping_path.is_absolute():
        mapping_path = (mappings_dir / mapping_path).resolve()

    mapping_config = load_json_file(mapping_path)
    mapping_config_dir = mapping_path.parent

    project_id = mapping["project_id"]
    dataset_id = mapping["dataset_id"]
    project = mgr.project_manager.load_project(project_id)
    dataset_config = mgr.dataset_manager.get_by_id(dataset_id)

    # Build mapping models for this dataset
    mapping_models = _build_mapping_models(
        mapping_config=mapping_config,
        mapping_config_dir=mapping_config_dir,
        dataset_config=dataset_config,
        project=project,
    )

    if not mapping_models:
        return

    # Register mappings and get registered mapping objects
    mapping_mgr = project.dimension_mapping_manager
    registered_mappings = _register_dimension_mappings(
        mapping_models=mapping_models,
        mapping_mgr=mapping_mgr,
        dataset_id=dataset_id,
    )

    # Query the dataset and create table
    _query_and_create_table(
        con=con,
        scenario=scenario,
        dataset_id=dataset_id,
        registered_mappings=registered_mappings,
        query_submitter=query_submitter,
        mgr=mgr,
        scratch_dir=scratch_dir,
    )


def _build_mapping_models(
    mapping_config: dict,
    mapping_config_dir: Path,
    dataset_config,
    project,
) -> list[MappingTableModel]:
    """Build MappingTableModel instances for a dataset's dimension mappings."""
    mapping_models = []

    for mapping_entry in mapping_config.get("mappings", []):
        dimension_type = DimensionType(mapping_entry["dimension_type"])
        mapping_type = mapping_entry.get("mapping_type", "many_to_one_aggregation")
        description = mapping_entry.get("description")

        csv_file = mapping_entry.get("file")
        if not csv_file:
            continue
        csv_path = Path(csv_file)
        if not csv_path.is_absolute():
            csv_path = (mapping_config_dir / csv_path).resolve()

        # Find matching project and dataset dimensions
        dims = _find_matching_dimensions(
            dimension_type=dimension_type,
            dataset_config=dataset_config,
            project=project,
        )
        if dims is None:
            msg = f"No matching dimensions found for dimension type {dimension_type}"
            raise InvalidParameter(msg)
        dataset_dim, project_dim = dims

        mapping_model = MappingTableModel(
            from_dimension=DimensionReferenceModel(
                dimension_id=dataset_dim.model.dimension_id,
                type=dataset_dim.model.dimension_type,
                version=dataset_dim.model.version,
            ),
            to_dimension=DimensionReferenceModel(
                dimension_id=project_dim.model.dimension_id,
                type=project_dim.model.dimension_type,
                version=project_dim.model.version,
            ),
            mapping_type=mapping_type,
            description=description,
            file=str(csv_path),
        )
        mapping_models.append(mapping_model)
        logger.debug("Prepared dimension mapping for {} from {}", dimension_type, csv_path)

    return mapping_models


def _find_matching_dimensions(
    dimension_type: DimensionType,
    dataset_config,
    project,
) -> tuple | None:
    """Find matching dataset and project dimensions for a dimension type.

    Returns
    -------
    tuple | None
        (dataset_dim, project_dim) if found, None otherwise
    """
    if dimension_type == DimensionType.METRIC:
        dataset_dim = dataset_config.get_dimension(dimension_type)
        project_dims = project.config.list_base_dimensions(dimension_type)
        project_dim = None
        for pdim in project_dims:
            if pdim.model.class_name == dataset_dim.model.class_name:
                project_dim = pdim
                break
        if project_dim is None:
            logger.warning(
                "No matching project dimension found for metric class_name={}",
                dataset_dim.model.class_name,
            )
            return None
    else:
        project_dims = project.config.list_base_dimensions(dimension_type)
        if not project_dims:
            logger.warning("No project dimension found for type {}", dimension_type)
            return None
        assert len(project_dims) == 1, f"Multiple project dimensions found: {project_dims}"
        project_dim = project_dims[0]
        dataset_dim = dataset_config.get_dimension(dimension_type)

    return dataset_dim, project_dim


def _register_dimension_mappings(
    mapping_models: list[MappingTableModel],
    mapping_mgr,
    dataset_id: str,
) -> list:
    """Register dimension mappings and return registered mapping objects."""
    mappings_data = {
        "mappings": [m.model_dump(mode="json", by_alias=True) for m in mapping_models]
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp_file:
        json.dump(mappings_data, tmp_file)
        tmp_path = Path(tmp_file.name)

    try:
        mapping_ids = mapping_mgr.register(
            tmp_path,
            submitter=getuser(),
            log_message=f"Registered dimension mappings for {dataset_id}",
        )
        registered_mappings = [mapping_mgr.get_by_id(x) for x in mapping_ids]
        logger.info("Registered {} dimension mappings for {}", len(mapping_models), dataset_id)
        return registered_mappings
    finally:
        tmp_path.unlink()


def _query_and_create_table(
    con: duckdb.DuckDBPyConnection,
    scenario: str,
    dataset_id: str,
    registered_mappings: list,
    query_submitter: DatasetQuerySubmitter,
    mgr: RegistryManager,
    scratch_dir: Path,
) -> None:
    """Query a dataset with mappings and create a DuckDB table."""
    to_dimension_references = [
        DimensionReferenceModel(
            dimension_id=m.model.to_dimension.dimension_id,
            type=m.model.to_dimension.dimension_type,
            version=m.model.to_dimension.version,
        )
        for m in registered_mappings
    ]

    query = make_dataset_query(
        name=dataset_id,
        dataset_id=dataset_id,
        to_dimension_references=to_dimension_references,
    )
    # This calls toPandas() because the duckdb connection inside dsgrid is
    # different than this one. We need to extract it and then add it through this connection.
    df = query_submitter.submit(  # noqa: F841
        query,
        mgr,
        scratch_dir=scratch_dir,
        overwrite=True,
    ).toPandas()
    base_id = dataset_id.split("__")[1]
    table_name = f"dsgrid_data.{scenario}__{base_id}__1_0_0"
    # Note: This overwrites the original table with the mapped table.
    con.sql(f"CREATE OR REPLACE TABLE {table_name} AS SELECT * FROM df")
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

        dataset_config = load_json_file(config_file_path)
        new_dataset_id = f"{scenario}__{table_name}"
        dataset_config["dataset_id"] = new_dataset_id
        config_dir = config_file_path.parent

        # Convert dimension file paths
        for dimension in dataset_config.get("dimensions", []):
            if "file" in dimension:
                file_path = Path(dimension["file"])
                if not file_path.is_absolute():
                    dimension["file"] = str((config_dir / file_path).resolve())

        data_file_path = dataset_config.get("data_layout", {}).get("data_file", {}).get("path")
        if data_file_path is not None:
            path = Path(data_file_path)
            if not path.is_absolute():
                dataset_config["data_layout"]["data_file"]["path"] = str(
                    (config_dir / path).resolve()
                )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp_file:
            json.dump(dataset_config, tmp_file)
            tmp_path = Path(tmp_file.name)
        try:
            mgr.dataset_manager.register(
                tmp_path,
                submitter=getuser(),
                log_message=f"Registered scenario dataset {new_dataset_id}",
            )
            logger.info("Registered scenario dataset {}", new_dataset_id)
        finally:
            tmp_path.unlink()


def _registry_url(registry_path: Path) -> str:
    return f"sqlite:///{registry_path}/registry.db"
