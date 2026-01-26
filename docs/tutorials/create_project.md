(create-project-tutorial)=

# Create a project

In this tutorial you will learn how to create and explore a stride project.

The tutorial assumes that you have cloned the stride repository to your local system in the
current directory (`./stride`).

 
1. Create the test project.


    ```{eval-rst}
    .. code-block:: console
    
        $ stride projects create stride/tests/data/project_input.json5 --dataset global-test
    ```

Upon successful completion there will be a directory called `test_project` in the current
directory. You will use this path for subsequent commands.

2. List the scenarios in the project. The test project include a baseline dataset as well
as a second scenario with customized GDP data.

    ```{eval-rst}
    .. code-block:: console
    
        $ stride scenarios list test_project
    ```
    
    ```{eval-rst}
    .. code-block:: console
    
        Scenarios in project with project_id=test_project:
          baseline
          alternate_gdp
    ```

3. List the data tables that are available in every scenario of each project.

    ```{eval-rst}
    .. code-block:: console

        $ stride data-tables list
    ```
    
    ```{eval-rst}
    .. code-block:: console
    
        energy_intensity gdp hdi load_shapes population
    ```

4. Display a portion of a data table in the console. This shows the differences
between the baseline and custom GDP tables.

    ```{eval-rst}
    .. code-block:: console

        $ stride data-tables show test_project gdp --scenario baseline
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
        │ 500000000000.0 │ country_1 │       2055 │
        │ 250000000000.0 │ country_2 │       2025 │
        │ 255000000000.0 │ country_2 │       2030 │
        │ 260000000000.0 │ country_2 │       2035 │
        │ 265000000000.0 │ country_2 │       2040 │
        │ 271000000000.0 │ country_2 │       2045 │
        │ 276000000000.0 │ country_2 │       2050 │
        │ 282000000000.0 │ country_2 │       2055 │
        ├────────────────┴───────────┴────────────┤
        │ 14 rows                       3 columns │
        └─────────────────────────────────────────┘
    ```
    
    ```{eval-rst}
    .. code-block:: console

        $ stride data-tables show test_project gdp --scenario alternate_gdp
    ```
    ```{eval-rst}
    .. code-block:: console
    
        ┌────────────────┬───────────┬────────────┐
        │     value      │ geography │ model_year │
        │     double     │  varchar  │   int64    │
        ├────────────────┼───────────┼────────────┤
        │ 510000000000.0 │ country_1 │       2025 │
        │ 510000000000.0 │ country_1 │       2030 │
        │ 510000000000.0 │ country_1 │       2035 │
        │ 510000000000.0 │ country_1 │       2040 │
        │ 510000000000.0 │ country_1 │       2045 │
        │ 510000000000.0 │ country_1 │       2050 │
        │ 510000000000.0 │ country_1 │       2055 │
        │ 260000000000.0 │ country_2 │       2025 │
        │ 265000000000.0 │ country_2 │       2030 │
        │ 270000000000.0 │ country_2 │       2035 │
        │ 275000000000.0 │ country_2 │       2040 │
        │ 281000000000.0 │ country_2 │       2045 │
        │ 286000000000.0 │ country_2 │       2050 │
        │ 292000000000.0 │ country_2 │       2055 │
        ├────────────────┴───────────┴────────────┤
        │ 14 rows                       3 columns │
        └─────────────────────────────────────────┘
    ```
