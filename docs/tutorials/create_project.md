(create-project-tutorial)=

# Create a project

In this tutorial you will learn how to create and explore a stride project.

This tutorial uses the ``global-test`` dataset which is a small test dataset. For real projects,
use the ``global`` dataset instead (omit the ``--dataset`` option).

## Discover available data

Before creating a project, you can explore what countries and years are available in the dataset.

List available countries:

```{eval-rst}
.. code-block:: console

    $ stride datasets list-countries --dataset global-test
    Countries available in the 'global-test' dataset (2 total):

      country_1
      country_2
```

List available model years:

```{eval-rst}
.. code-block:: console

    $ stride datasets list-model-years --dataset global-test
```

List available weather years:

```{eval-rst}
.. code-block:: console

    $ stride datasets list-weather-years --dataset global-test
```

## Create the project

1. Create a project configuration file using the ``stride projects init`` command.

    ```{eval-rst}
    .. code-block:: console

        $ stride projects init --country country_1 -o my_project.json5
    ```

    This creates a JSON5 configuration file with default settings. You can edit this file to
    customize the project ID, description, model years, and scenarios.

2. Create the project from the configuration file.

    ```{eval-rst}
    .. code-block:: console

        $ stride projects create my_project.json5 --dataset global-test
    ```

Upon successful completion there will be a directory called ``country_1_project`` in the current
directory. You will use this path for subsequent commands.

3. List the scenarios in the project. The default template includes a baseline scenario and
an EV projection scenario.

    ```{eval-rst}
    .. code-block:: console

        $ stride scenarios list country_1_project
    ```

    ```{eval-rst}
    .. code-block:: console

        Scenarios in project with project_id=country_1_project:
          baseline
          ev_projection
    ```

4. List the data tables that are available in every scenario of each project.

    ```{eval-rst}
    .. code-block:: console

        $ stride data-tables list
    ```

    ```{eval-rst}
    .. code-block:: console

        energy_intensity gdp hdi load_shapes population
    ```

5. Display a portion of a data table in the console.

    ```{eval-rst}
    .. code-block:: console

        $ stride data-tables show country_1_project gdp --scenario baseline
    ```
    ```{eval-rst}
    .. code-block:: console

        ┌────────────────┬───────────┬────────────┐
        │     value      │ geography │ model_year │
        │     double     │  varchar  │   int64    │
        ├────────────────┼───────────┼────────────┤
        │ 500000000000.0 │ country_1 │       2025 │
        │ 500000000000.0 │ country_1 │       2030 │
        │ 500000000000.0 │ country_1 │       2035 │
        │ 500000000000.0 │ country_1 │       2040 │
        │ 500000000000.0 │ country_1 │       2045 │
        │ 500000000000.0 │ country_1 │       2050 │
        ├────────────────┴───────────┴────────────┤
        │ 6 rows                        3 columns │
        └─────────────────────────────────────────┘
    ```
