# Manage calculated tables

Stride calculates several intermediate tables in order to create the final energy projection table.
The user can override any of these intermediate tables.

This tutorial will teach you how to view, export, and override these tables. The tutorial
requires the test project which you can get by cloning the stride repository to your
local system with git and running the `projects create` command.

Assumptions:
- The stride package is installed in the current Python virtual environment.
- The stride repository is in the current directory at `./stride`.

```{eval-rst}
.. code-block:: console

    $ stride projects create stride/tests/data/project_input.json
```

Now the test project is stored at `./test_project`. All commands below will use that
directory.

## List calculated tables
This command will list the calculated tables in the project.

```{eval-rst}
.. code-block:: console

    $ stride calculated-tables list test_project
```
```
Calculated tables for all scenarios:
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
  gdp_country
  hdi_country
  load_shapes_com_ind_tra
  load_shapes_res
  population_country

Override tables by scenario:
  Scenario: baseline
    None

  Scenario: alternate_gdp
    None
```

## Show a calculated table
This command will print a subset of rows of one table to the console.

```{eval-rst}
.. code-block:: console

    $ stride calculated-tables show test_project energy_projection_res_load_shapes
```
```
┌──────────────────────────┬────────────┬───────────┬─────────────┬─────────┬────────────────────┐
│        timestamp         │ model_year │ geography │   sector    │ metric  │       value        │
│ timestamp with time zone │   int64    │  varchar  │   varchar   │ varchar │       double       │
├──────────────────────────┼────────────┼───────────┼─────────────┼─────────┼────────────────────┤
│ 2018-12-31 21:00:00-07   │       2055 │ country_1 │ residential │ other   │ 12601436.961372659 │
│ 2018-01-30 22:00:00-07   │       2055 │ country_1 │ residential │ other   │ 12601436.961372659 │
│ 2018-01-30 23:00:00-07   │       2055 │ country_1 │ residential │ other   │ 11341293.265235394 │
│ 2018-01-31 00:00:00-07   │       2055 │ country_1 │ residential │ other   │ 11341293.265235394 │
│ 2018-01-31 01:00:00-07   │       2055 │ country_1 │ residential │ other   │ 11971365.113304026 │
│ 2018-01-31 02:00:00-07   │       2055 │ country_1 │ residential │ other   │ 12601436.961372659 │
│ 2018-01-31 03:00:00-07   │       2055 │ country_1 │ residential │ other   │ 13861580.657509925 │
│ 2018-01-31 04:00:00-07   │       2055 │ country_1 │ residential │ other   │ 15751796.201715825 │
│ 2018-01-31 05:00:00-07   │       2055 │ country_1 │ residential │ other   │ 17642011.745921724 │
│ 2018-01-31 06:00:00-07   │       2055 │ country_1 │ residential │ other   │ 17642011.745921724 │
│ 2018-01-31 07:00:00-07   │       2055 │ country_1 │ residential │ other   │ 16381868.049784457 │
│ 2018-01-31 08:00:00-07   │       2055 │ country_1 │ residential │ other   │ 15121724.353647191 │
│ 2018-01-31 09:00:00-07   │       2055 │ country_1 │ residential │ other   │ 15121724.353647191 │
│ 2018-01-31 10:00:00-07   │       2055 │ country_1 │ residential │ other   │ 16066832.125750141 │
│ 2018-01-31 11:00:00-07   │       2055 │ country_1 │ residential │ other   │  17011939.89785309 │
│ 2018-01-31 12:00:00-07   │       2055 │ country_1 │ residential │ other   │ 18272083.593990356 │
│ 2018-01-31 13:00:00-07   │       2055 │ country_1 │ residential │ other   │ 20162299.138196256 │
│ 2018-01-31 14:00:00-07   │       2055 │ country_1 │ residential │ other   │ 20162299.138196256 │
│ 2018-01-31 15:00:00-07   │       2055 │ country_1 │ residential │ other   │ 18902155.442058988 │
│ 2018-01-31 16:00:00-07   │       2055 │ country_1 │ residential │ other   │ 15751796.201715825 │
├──────────────────────────┴────────────┴───────────┴─────────────┴─────────┴────────────────────┤
│ 20 rows                                                                              6 columns │
└────────────────────────────────────────────────────────────────────────────────────────────────┘
```

## Export a calculated table
This command will export a calculated table to a file. The file format is determined by the
extension passed. By default, stride uses `".csv"`. You can also choose `".parquet"`.

Note that you must pass a scenario name with `-s` or `--scenario`.

```{eval-rst}
.. code-block:: console

    $ stride calculated-tables export test_project -s alternate_gdp -t energy_projection_res_load_shapes
```
```
2025-08-20 07:52:35.415 | INFO     | stride.project:export_calculated_table:272 - Exported scenario=alternate_gdp table=energy_projection_res_load_shapes to energy_projection_res_load_shapes.csv
```

## Override a calculated table
This command will override the table used for computing energy projection. Let's assume that
we have modified the file exported in the previous step.

```{eval-rst}
.. note:: stride will check the schema of the file you pass. The column names and data types must
   match the existing table.
```

```{eval-rst}
.. code-block:: console

    $ stride calculated-tables override test_project -s alternate_gdp -t energy_projection_res_load_shapes -f energy_projection_res_load_shapes.csv
```
```
2025-08-20 07:58:32.901 | INFO     | stride.project:override_calculated_tables:178 - Added override table energy_projection_res_load_shapes to scenario alternate_gdp
2025-08-20 07:58:32.925 | INFO     | stride.project:compute_energy_projection:336 - Run scenario=baseline dbt models with 'dbt run --vars {"scenario": "baseline", "country": "country_1", "model_years": "(2025,2030,2035,2040,2045,2050,2055)"}'
```
This output is truncated. You will see additional logging about `dbt` rebuilding the tables.

You will now see different output values when running the stride UI.
