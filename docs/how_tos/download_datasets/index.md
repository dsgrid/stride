(download-datasets)=
# Download Datasets

STRIDE provides a CLI command to download datasets from remote repositories. This guide shows how
to download pre-configured datasets as well as custom datasets from GitHub.

## Prerequisites

- STRIDE installed and available in your environment
- For private repositories: GitHub CLI (`gh`) installed and authenticated

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

To download a known dataset to the default location (``~/.stride/data``):

```{eval-rst}

.. code-block:: console

   $ stride datasets download global
```

This single command downloads both the full ``global`` dataset and the smaller ``global-test``
subset from the same release archive. The test dataset enables the ``--use-test-data`` option
when creating projects, which is useful for faster iteration during development.

### Specify a Destination Directory

Use the ``-d`` or ``--destination`` option to download to a specific location:

```{eval-rst}

.. code-block:: console

   $ stride datasets download global -d ./my_data
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

For private repositories, STRIDE automatically uses your GitHub CLI authentication. Ensure you are
logged in:

```{eval-rst}

.. code-block:: console

   $ gh auth status
```

If not authenticated, run:

```{eval-rst}

.. code-block:: console

   $ gh auth login
```
