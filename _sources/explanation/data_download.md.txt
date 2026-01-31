(data-download)=
# Data Download

STRIDE retrieves input datasets from remote repositories, typically GitHub releases. This page explains how the download system works and how to use it.

## Default Data Repository

STRIDE uses the [dsgrid/stride-data](https://github.com/dsgrid/stride-data) repository as its primary data source. This repository contains:

- **global** - Full dataset for all supported countries
- **global-test** - Smaller test dataset for development and testing

## How Downloads Work

The download system follows this flow:

1. **Query GitHub API** - Fetch available release versions from the repository
2. **Select Version** - Use the latest release by default, or specify a version
3. **Download Archive** - Retrieve the release tarball
4. **Extract and Install** - Extract to `~/.stride/data/<dataset-name>/`

### Authentication

STRIDE attempts to use the GitHub CLI (`gh`) for authentication when available. This is useful for:

- Private repositories
- Avoiding rate limits on public repositories

If the GitHub CLI is not installed or authenticated, STRIDE falls back to unauthenticated API requests.

## CLI Commands

### List Available Datasets

```bash
stride datasets list-remote
```

This shows all known datasets with their available versions.

### Download a Dataset

```bash
# Download the global dataset (latest version)
# This automatically includes the global-test subset
stride datasets download global

# Download a specific version
stride datasets download global --version v0.2.0
```

### Download from a Custom Repository

For advanced use cases, you can download from any GitHub repository:

```bash
stride datasets download --url dsgrid/my-custom-data --subdirectory my-subset
```

## Storage Location

Downloaded datasets are stored in the data directory, which is determined by (in order of precedence):

1. The `--data-dir` CLI option
2. The `STRIDE_DATA_DIR` environment variable
3. The default location: `~/.stride/data/`

```
~/.stride/data/
├── global/
│   ├── dimension_mappings.json5
│   ├── energy_intensity/
│   ├── gdp/
│   ├── load_shapes/
│   └── ...
└── global-test/
    └── ...
```

### Custom Data Directory

To use a custom data directory persistently, set the `STRIDE_DATA_DIR` environment variable:

```bash
export STRIDE_DATA_DIR=/path/to/my/data
stride datasets download global
stride projects create my_config.json5
```

Or specify it per-command with the `--data-dir` option:

```bash
stride datasets download global --data-dir /path/to/my/data
stride projects create my_config.json5 --data-dir /path/to/my/data
```

## Using Test Data

When creating a project, you can use the smaller test dataset for faster iteration:

```{eval-rst}

.. tabs::

  .. tab:: CLI

     .. code-block:: console

        # Use test data for development
        $ stride projects create my_config.json5 --dataset global-test

        # Use full data for production
        $ stride projects create my_config.json5

  .. tab:: Python

     .. code-block:: python

        from stride import Project

        # Use test data for development
        project = Project.create("my_config.json5", dataset="global-test")

        # Use full data for production
        project = Project.create("my_config.json5")
```

The test dataset contains the same structure but with reduced data volume, making it suitable for:

- Development and debugging
- CI/CD pipelines
- Learning the STRIDE workflow

## Error Handling

Common download issues:

- **Dataset not found** - Ensure the dataset name matches a known dataset or provide a valid `--url`
- **Authentication required** - Install and authenticate the GitHub CLI with `gh auth login`
- **Destination exists** - Remove the existing dataset directory before downloading again
