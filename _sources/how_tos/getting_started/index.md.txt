(getting-started)=
# Getting Started

## Installation

1. Install Python 3.11 or later.

2. Create a Python 3.11+ virtual environment. This example uses the ``venv`` module in the standard
library to create a virtual environment in your current directory. You may prefer a single
`python-envs` in your home directory instead of the current directory. You may also prefer ``conda``
or ``mamba``.

    ```{eval-rst}
    
    .. code-block:: console
    
       $ python -m venv .venv
    ```

3. Activate the virtual environment.

    ```{eval-rst}

    .. tabs::

      .. code-tab:: console UNIX

         $ source .venv/bin/activate

      .. code-tab:: console Windows Command Prompt

         $ .venv\Scripts\activate

      .. code-tab:: console Windows PowerShell

         $ .venv\Scripts\Activate.ps1
    ```

    Whenever you are done using stride, you can deactivate the environment by running ``deactivate``.

4. Install the Python package `stride`.

    ```{eval-rst}
    
    .. tabs::

      .. code-tab:: console pip PyPI

        $ pip install stride-load-forecast
      
      .. code-tab:: console pip git+http

        $ pip install git+https://github.com/dsgrid/stride
    
      .. code-tab:: console clone http
    
        $ git clone https://github.com/dsgrid/stride.git
        $ cd stride
        $ pip install -e stride

        Note: The "editable" installation option (`-e`) is required.
    
      .. code-tab:: console clone ssh
    
        $ git clone git@github.com:dsgrid/stride.git
        $ cd stride
        $ pip install -e stride

        Note: The "editable" installation option (`-e`) is required.
    ```
    
## Typical Workflow

1. {ref}`download-datasets`
2. {ref}`create-project-tutorial`
3. {ref}`Explore project data on the command line <explore-data-cli>`
4. {ref}`visually-inspect`
5. {ref}`Modify a project <manage-calculated-tables>`
6. {ref}`Export data <export-dataset>`
7. {ref}`Access data programmatically <data-api-tutorial>`
