import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

from dsgrid.query.models import DimensionReferenceModel, make_dataset_query
import duckdb
from dsgrid.config.dataset_config import DataSchemaType
from dsgrid.dimension.base_models import DimensionType
from dsgrid.query.query_submitter import (
    DatasetQuerySubmitter,
)
import json5
from dsgrid.config.registration_models import (
    RegistrationModel,
    ProjectRegistrationModel,
    DatasetRegistrationModel,
)
from dsgrid.registry.bulk_register import bulk_register
from dsgrid.registry.common import DataStoreType, DatabaseConnection
from dsgrid.registry.registry_manager import RegistryManager
from loguru import logger

from stride.io import create_table_from_file
from stride.models import DatasetConfig


def deploy_to_dsgrid_registry(
    base_path: Path, project_config: dict[str, Any], datasets: list[DatasetConfig]
) -> None:
    """Deploy the Stride project to a dsgrid registry."""
    mgr = create_dsgrid_registry(base_path)
    create_project_directory_structure(base_path, project_config)
    datasets_data_path = base_path / "datasets"
    datasets_data_path.mkdir()
    dataset_paths = write_datasets_to_dsgrid_format(mgr, base_path, datasets_data_path, datasets)
    _bulk_register(mgr, base_path, dataset_paths)


def create_dsgrid_registry(base_path: Path) -> RegistryManager:
    """Create a dsgrid registry."""
    url = _registry_url(base_path)
    data_dir = base_path / "registry_data"
    conn = DatabaseConnection(url=url)
    return RegistryManager.create(
        conn, data_dir, data_store_type=DataStoreType.DUCKDB, overwrite=True
    )


def _bulk_register(
    mgr: RegistryManager,
    base_path: Path,
    dataset_paths: list[dict[str, Any]],
) -> None:
    """Register the project and all datasets."""
    bulk_config = _make_bulk_registration_config(base_path, dataset_paths)
    bulk_config_file = base_path / "registration.json5"
    bulk_config.to_file(bulk_config_file)
    skip_checks = False
    try:
        bulk_register(mgr, bulk_config_file)
    finally:
        if skip_checks:
            os.environ.pop("__DSGRID_SKIP_CHECK_DATASET_TO_PROJECT_MAPPING__")


def _make_bulk_registration_config(
    base_path: Path,
    dataset_paths: list[dict[str, Any]],
) -> RegistrationModel:
    """Create a bulk registration config file from a project and datasets."""
    project_file = _project_config_path(base_path)
    project_config = json5.loads(project_file.read_text(encoding="utf-8"))
    project_id = project_config["project_id"]
    return RegistrationModel(
        projects=[
            ProjectRegistrationModel(
                project_id=project_id,
                config_file=project_file,
            )
        ],
        datasets=[
            DatasetRegistrationModel(
                dataset_id=x["dataset_id"],
                config_file=x["config_file"],
                dataset_path=x["dataset_path"],
            )
            for x in dataset_paths
        ],
        dataset_submissions=[],
    )


def make_mapped_datasets(
    con: duckdb.DuckDBPyConnection,
    base_path: Path,
    project_id: str,
    scenario: str,
) -> None:
    url = _registry_url(base_path)
    mgr = RegistryManager.load(DatabaseConnection(url=url))
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


def _registry_url(base_path: Path) -> str:
    return f"sqlite:///{base_path}/registry.db"


def _dsg_base_path(base_path: Path) -> Path:
    return base_path / "dsgrid_project"


def _datasets_config_path(base_path: Path) -> Path:
    return _dsg_base_path(base_path) / "datasets"


def _dataset_config_path(base_path: Path, dataset_id: str) -> Path:
    return _datasets_config_path(base_path) / dataset_id / "dataset.json5"


def _project_config_path(base_path: Path) -> Path:
    return _dsg_base_path(base_path) / "project" / "project.json5"


def create_project_directory_structure(base_path: Path, project_config: dict[str, Any]) -> Path:
    dsg_base_path = _dsg_base_path(base_path)
    dsg_project_path = dsg_base_path / "project"
    dsg_datasets_path = dsg_base_path / "datasets"
    dsg_project_path.mkdir(parents=True)
    dsg_datasets_path.mkdir(parents=True)
    project_file = _project_config_path(base_path)
    project_file.write_text(json5.dumps(project_config, indent=2), encoding="utf-8")
    return dsg_base_path


def write_datasets_to_dsgrid_format(
    mgr: RegistryManager,
    base_path: Path,
    datasets_data_path: Path,
    datasets: list[DatasetConfig],
) -> list[dict[str, Any]]:
    """Write the datasets to files in dsgrid format.
    This converts CSV to Parquet and converts custom column names to dimension types.
    The function lets DuckDB infer data types. Could add schemas if necessary.
    """
    con = duckdb.connect()
    dataset_paths: list[dict[str, Any]] = []
    for dataset in datasets:
        dataset_data_path = datasets_data_path / dataset.dataset_id
        dataset_data_path.mkdir()
        included_dimensions = [x for x in dataset.dimension_columns.values()]
        if dataset.time_type is not None:
            included_dimensions.append(DimensionType.TIME)
        rel = create_table_from_file(con, dataset.dataset_id, dataset.path)
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
            rel = con.sql(f"SELECT {cols} FROM {rel.alias}")

        dst = dataset_data_path / "table.parquet"
        rel.to_parquet(str(dst))
        if dataset.missing_associations_file is not None:
            dst = (
                dataset_data_path
                / f"missing_associations{dataset.missing_associations_file.suffix}"
            )
            shutil.copyfile(dataset.missing_associations_file, dst)
        logger.info("Wrote dataset {} to dsgrid format at {}", dataset.dataset_id, dst)

        config_file = _dataset_config_path(base_path, dataset.dataset_id)
        config_file.parent.mkdir()
        generate_dsgrid_dataset_config_file(dataset, config_file)
        dataset_paths.append(
            {
                "dataset_id": dataset.dataset_id,
                "config_file": _dataset_config_path(base_path, dataset.dataset_id),
                "dataset_path": dataset_data_path,
                "base_dataset_id": dataset.dataset_id.split("__")[1],
            }
        )

    return dataset_paths


def generate_dsgrid_dataset_config_file(dataset: DatasetConfig, config_file: Path) -> None:
    # dsgrid has a function to do this, but there are too many dimension-specific things here.
    config = {
        "dataset_id": dataset.dataset_id,
        "dimensions": dataset.dimensions,
        "trivial_dimensions": [x.value for x in dataset.trivial_dimensions],
        "dataset_type": "modeled",
        "data_schema": {
            "data_schema_type": DataSchemaType.ONE_TABLE.value,
            "table_format": {"format_type": "unpivoted"},
        },
        "version": "1.0.0",
        "description": "",
        "origin_creator": "",
        "origin_organization": "",
        "origin_date": "",
        "origin_project": "",
        "origin_version": "",
        "data_source": "",
        "source": "",
        "data_classification": "moderate",
        "use_project_geography_time_zone": False,
        "tags": [],
        "user_defined_metadata": {},
    }
    config_file.write_text(json5.dumps(config, indent=2), encoding="utf-8")
