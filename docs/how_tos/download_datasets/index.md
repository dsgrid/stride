(download-datasets)=
# Download Datasets

STRIDE provides a CLI command to download datasets from remote repositories. This guide shows how
to download pre-configured datasets as well as custom datasets from GitHub.

## Prerequisites

- STRIDE installed and available in your environment
- For private repositories: GitHub CLI (`gh`) installed and authenticated
- For public repositories: No additional tools required (uses Python's built-in urllib)

## List Available Datasets

To see the known datasets available for download along with their available versions:

```{eval-rst}

.. code-block:: console

   $ stride datasets list-remote
```

This will display each dataset's name, repository, subdirectory, description, and available
versions. Datasets may also have an associated test dataset (shown as ``test_subdirectory``)
which is automatically downloaded alongside the main dataset.

## Download a Known Dataset

To download a known dataset to the default location (``~/.stride/data`` or ``STRIDE_DATA_DIR``):

```{eval-rst}

.. code-block:: console

   $ stride datasets download global
```

This single command downloads both the full ``global`` dataset and the smaller ``global-test``
subset from the same release archive. The test dataset enables faster iteration during development.

### Specify a Data Directory

Use the ``-d`` or ``--data-dir`` option to download to a specific location:

```{eval-rst}

.. code-block:: console

   $ stride datasets download global -d ./my_data
```

Alternatively, set the ``STRIDE_DATA_DIR`` environment variable for a persistent default:

```{eval-rst}

.. code-block:: console

   $ export STRIDE_DATA_DIR=/path/to/data
   $ stride datasets download global
```

### Specify a Version

By default, the latest release is downloaded. To download a specific version:

```{eval-rst}

.. code-block:: console

   $ stride datasets download global -v v0.2.0
```

## Download from a Custom Repository

To download a dataset from any GitHub repository, use the ``--url`` and ``--subdirectory`` options:

```{eval-rst}

.. code-block:: console

   $ stride datasets download --url https://github.com/owner/repo --subdirectory data
```

```{eval-rst}
.. note::
   The ``--subdirectory`` option is required when using ``--url``.
```

## Private Repository Authentication

For public repositories like ``dsgrid/stride-data``, no authentication is required. STRIDE will
download using Python's built-in urllib library.

For private repositories, STRIDE uses your GitHub CLI authentication. Ensure you are logged in:

```{eval-rst}

.. code-block:: console

   $ gh auth status
```

If not authenticated, run:

```{eval-rst}

.. code-block:: console

   $ gh auth login
```

## Alternative: Clone the Repository Directly

If you don't have the GitHub CLI (``gh``) installed, you can clone the stride-data repository
directly using git:

```{eval-rst}

.. code-block:: console

   $ git clone https://github.com/dsgrid/stride-data.git
   $ mkdir -p ~/.stride/data
   $ cp -r stride-data/global ~/.stride/data/
   $ cp -r stride-data/global-test ~/.stride/data/
```

Alternatively, you can set the ``STRIDE_DATA_DIR`` environment variable to point to the cloned
repository location:

```{eval-rst}

.. code-block:: console

   $ git clone https://github.com/dsgrid/stride-data.git
   $ export STRIDE_DATA_DIR=/path/to/stride-data
```

This approach is useful if you want to keep the dataset in a custom location or if you're
working in an environment where ``gh`` is not available.
