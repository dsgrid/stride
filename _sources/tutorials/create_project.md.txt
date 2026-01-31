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
    customize the project ID, description, model years, scenarios, and model parameters
    (such as heating/cooling thresholds and shoulder month smoothing).

2. Create the project from the configuration file.

    ```{eval-rst}
    .. code-block:: console

        $ stride projects create my_project.json5 --dataset global-test
    ```

Upon successful completion there will be a directory called ``country_1_project`` in the current
directory. You will use this path for subsequent commands.

(explore-data-cli)=
## Explore project data

There are several commands for exploring project data from the command line. For example:

1. List the scenarios in the project. The default template includes a baseline scenario and
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

2. List the data tables that are available in every scenario of each project.

    ```{eval-rst}
    .. code-block:: console

        $ stride data-tables list
    ```

    ```{eval-rst}
    .. code-block:: console

        energy_intensity gdp hdi load_shapes population
    ```

3. Display a portion of a data table in the console.

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

4. List calculated tables.

    ```{eval-rst}
    .. code-block:: console

        $ stride calculated-tables list country_1_project
    ```

    ```{eval-rst}
    .. code-block:: console

        Calculated tables for all scenarios:
          electricity_per_vehicle_km_country
          energy_intensity_com_ind_tra
          energy_intensity_com_ind_tra_gdp
          energy_intensity_com_ind_tra_gdp_applied_regression
          energy_intensity_com_ind_tra_pivoted
          energy_intensity_parsed
          energy_intensity_res
          energy_intensity_res_hdi
          energy_intensity_res_hdi_population
          energy_intensity_res_hdi_population_applied_regression
          energy_intensity_res_pivoted
          energy_projection
          energy_projection_com_ind_tra_load_shapes
          energy_projection_res_load_shapes
          ev_annual_energy_tj
          ev_energy_by_type
          ev_stock_share_country
          ev_stock_split
          ev_stock_total
          gdp_country
          hdi_country
          km_per_vehicle_year_applied
          km_per_vehicle_year_parsed
          km_per_vehicle_year_pivoted
          load_shapes_expanded
          phev_share_country
          population_country
          temperature_multipliers
          vehicle_per_capita_parsed
          vehicle_per_capita_pivoted
          vehicle_per_capita_population
          vehicle_stock_total
          weather_bait_daily
          weather_degree_days
          weather_degree_days_grouped

        Override tables by scenario:
          Scenario: baseline
            None

          Scenario: ev_projection
            None
    ```

5. Display a portion of a calculated table in the console.

    ```{eval-rst}
    .. code-block:: console

        $ stride calculated-tables show -s ev_projection country_1_project energy_projection
    ```

    ```{eval-rst}
    .. code-block:: console

        ┌─────────────────────┬────────────┬───────────┬────────────┬─────────┬────────────────────┬───────────────┐
        │      timestamp      │ model_year │ geography │   sector   │ metric  │       value        │   scenario    │
        │      timestamp      │   int64    │  varchar  │  varchar   │ varchar │       double       │    varchar    │
        ├─────────────────────┼────────────┼───────────┼────────────┼─────────┼────────────────────┼───────────────┤
        │ 2018-01-31 17:00:00 │       2025 │ country_1 │ Industrial │ other   │  67.02282323645481 │ ev_projection │
        │ 2018-03-30 01:00:00 │       2025 │ country_1 │ Industrial │ other   │  61.76006113474705 │ ev_projection │
        │ 2018-03-30 07:00:00 │       2025 │ country_1 │ Industrial │ other   │  65.62973915070864 │ ev_projection │
        │ 2018-03-30 21:00:00 │       2025 │ country_1 │ Industrial │ other   │ 63.849687263366306 │ ev_projection │
        │ 2018-04-30 07:00:00 │       2025 │ country_1 │ Industrial │ other   │  63.46271946177015 │ ev_projection │
        │ 2018-04-30 14:00:00 │       2025 │ country_1 │ Industrial │ other   │   62.6113902982586 │ ev_projection │
        │ 2018-04-30 22:00:00 │       2025 │ country_1 │ Industrial │ other   │  60.83133841091626 │ ev_projection │
        │ 2018-05-31 10:00:00 │       2025 │ country_1 │ Industrial │ other   │  64.39144218560092 │ ev_projection │
        │ 2018-05-31 15:00:00 │       2025 │ country_1 │ Industrial │ other   │  64.62362286655862 │ ev_projection │
        │ 2018-06-29 07:00:00 │       2025 │ country_1 │ Industrial │ other   │  65.55234559038941 │ ev_projection │
        │ 2018-06-29 08:00:00 │       2025 │ country_1 │ Industrial │ other   │   66.0167069523048 │ ev_projection │
        │ 2018-06-29 22:00:00 │       2025 │ country_1 │ Industrial │ other   │  62.53399673793936 │ ev_projection │
        │ 2018-07-31 14:00:00 │       2025 │ country_1 │ Industrial │ other   │  61.83745469506628 │ ev_projection │
        │ 2018-09-30 01:00:00 │       2025 │ country_1 │ Industrial │ other   │  61.45048689347012 │ ev_projection │
        │ 2018-09-30 02:00:00 │       2025 │ country_1 │ Industrial │ other   │ 61.373093333150884 │ ev_projection │
        │ 2018-09-30 03:00:00 │       2025 │ country_1 │ Industrial │ other   │  61.45048689347012 │ ev_projection │
        │ 2018-09-30 04:00:00 │       2025 │ country_1 │ Industrial │ other   │  61.83745469506628 │ ev_projection │
        │ 2018-09-30 06:00:00 │       2025 │ country_1 │ Industrial │ other   │  64.15926150464324 │ ev_projection │
        │ 2018-09-30 11:00:00 │       2025 │ country_1 │ Industrial │ other   │  65.01059066815479 │ ev_projection │
        │ 2018-09-30 12:00:00 │       2025 │ country_1 │ Industrial │ other   │   64.5462293062394 │ ev_projection │
        ├─────────────────────┴────────────┴───────────┴────────────┴─────────┴────────────────────┴───────────────┤
        │ 20 rows                                                                                        7 columns │
        └──────────────────────────────────────────────────────────────────────────────────────────────────────────┘    
    ```

```{eval-rst}
.. _export-dataset:
```

6. **Export the final dataset to file**

    The `energy_projection` table is the final table of results and can be exported for all scenarios to `energy_projection.csv` with the command:

    ```{eval-rst}
    .. code-block:: console

        $ stride projects export-energy-projection country_1_project
    ```

    To programmatically access specific views of the data, see the {ref}`data-api`.

(visually-inspect)=
## Visually inspect project data

The project data can be visually inspected by running the command:

```{eval-rst}
.. code-block:: console

    $ stride view country_1_project
```

And then opening the displayed address in a web browser:

```{eval-rst}
.. code-block:: console

    Dash is running on http://127.0.0.1:8050/

      * Serving Flask app 'STRIDE'
      * Debug mode: off
    WARNING: This is a development server. Do not use it in a production deployment. Use a production WSGI server instead.
      * Running on http://127.0.0.1:8050
    Press CTRL+C to quit
```

## Learn More

- {ref}`cli-reference`
- {ref}`data-api`
- {ref}`dbt-projet`
- {ref}`weather-year-modeling`
- {ref}`manage-calculated-tables`