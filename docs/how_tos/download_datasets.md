(download-datasets)=
# Download datasets

## Prerequisites

- STRIDE installed and available in your environment
- For private repositories: GitHub CLI (`gh`) installed and authenticated

## List available datasets

```{eval-rst}

.. code-block:: console

   $ stride datasets list-remote
```

## Download a known dataset

```{eval-rst}

.. code-block:: console

   $ stride datasets download global
```

This downloads to ``~/.stride/data`` (or ``STRIDE_DATA_DIR`` if set). Both the full dataset
and its test subset are downloaded automatically.

## Specify a version

```{eval-rst}

.. code-block:: console

   $ stride datasets download global -v v0.2.0
```

## Specify a data directory

```{eval-rst}

.. code-block:: console

   $ stride datasets download global -d /path/to/data
```

Or set the environment variable:

```{eval-rst}

  .. tabs::

    .. code-tab:: bash Mac/Linux

       $ export STRIDE_DATA_DIR=/path/to/data

    .. code-tab:: bash Windows Command Prompt

       $ set STRIDE_DATA_DIR=/path/to/data

    .. code-tab:: powershell Windows PowerShell

       $ $Env:STRIDE_DATA_DIR = "/path/to/data"
```

## Download from a custom repository

```{eval-rst}

.. code-block:: console

   $ stride datasets download --url https://github.com/owner/repo --subdirectory data
```

```{eval-rst}
.. note::
   The ``--subdirectory`` option is required when using ``--url``.
```

## Private repositories

Authenticate with GitHub CLI first:

```{eval-rst}

.. code-block:: console

   $ gh auth login
```

## Alternative: Clone directly

If ``gh`` is not available:

```{eval-rst}

  .. tabs::

    .. code-tab:: bash Mac/Linux

       $ git clone https://github.com/dsgrid/stride-data.git
       $ export STRIDE_DATA_DIR=/path/to/stride-data

    .. code-tab:: bash Windows Command Prompt

       $ git clone https://github.com/dsgrid/stride-data.git
       $ set STRIDE_DATA_DIR=/path/to/stride-data

    .. code-tab:: powershell Windows PowerShell

       $ git clone https://github.com/dsgrid/stride-data.git
       $ $Env:STRIDE_DATA_DIR = "/path/to/stride-data"
```

Or copy to the default location:

```{eval-rst}

.. code-block:: console

   $ git clone https://github.com/dsgrid/stride-data.git
   $ mkdir -p ~/.stride/data
   $ cp -r stride-data/global ~/.stride/data/
   $ cp -r stride-data/global-test ~/.stride/data/
```

## Background

Known datasets are hosted in the public [stride-data](https://github.com/dsgrid/stride-data)
repository. The ``list-remote`` command displays each dataset's name, repository, subdirectory,
description, and available versions. Datasets may have an associated test subset (shown as
``test_subdirectory``) which is downloaded automatically alongside the main dataset.

For private repositories, STRIDE uses GitHub CLI authentication. Check your authentication
status with:

```{eval-rst}

.. code-block:: console

   $ gh auth status
```

## Learn more

- {ref}`cli-reference`
