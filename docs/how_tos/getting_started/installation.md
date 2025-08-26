
```{eval-rst}
.. _installation:
```

# Installation

1. Install Python 3.11 or later.

2. Create a Python 3.11+ virtual environment. This example uses the ``venv`` module in the standard
library to create a virtual environment in your current directory. You may prefer a single
`python-envs` in your home directory instead of the current directory. You may also prefer ``conda``
or ``mamba``.

    ```{eval-rst}
    
    .. code-block:: console
    
       $ python -m venv stride-env
    ```

3. Activate the virtual environment.

    ```{eval-rst}
    
    .. tabs::
    
      .. code-tab:: console UNIX
     
         $ source stride-env/bin/activate
    
      .. code-tab:: console Windows
    
         $ .\stride-env\Scripts\activate
    ```

Whenever you are done using stride, you can deactivate the environment by running ``deactivate``.

4. Install the Python package `stride`.

    ```{eval-rst}
    
    .. tabs::
    
      .. code-tab:: console http
    
        $ git clone https://github.com/dsgrid/stride.git
    
      .. code-tab:: console ssh
    
        $ git clone git@github.com:dsgrid/stride.git
    ```
    
    ```{eval-rst}
    .. note:: The "editable" installation option is required.
    ```
    
    ```{eval-rst}
    .. code-block:: console
    
        $ pip install -e stride
    ```
