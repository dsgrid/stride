# DBT project
Stride uses [dbt](https://github.com/dbt-labs/dbt-core) to build its energy projection tables.
This tutorial will teach you how to run `dbt` commands in a project directory.

1. Create the test project as described at {ref}`create-project-tutorial`.

2. Change to the `dbt` directory.

    ```{eval-rst}
    .. code-block:: console
    
        $ cd test_project/dbt
    ```
    
    - The file `dbt_project.yml` defines the project.
    
    - The `models` directory defines several `.sql` files. Each of these files defines an intermediate
    view in the overall workflow graph. These SQL queries perform computations on the source datasets in
    order to build the energy projection table.

3. Generate the `dbt` documentation site. This requires the same `dbt` command that stride
used to build each project scenario. You will see a command like the example below in your
console or in the `stride.log` file, which should be in your current directory.

    It is not necessary to run this command. It is only shown in order to demonstrate how to run the
    next command for your specific scenario and model_years.
 
    ```{eval-rst}
    .. code-block:: console
    
        $ dbt run --vars '{"scenario": "baseline", "country": "country_1", "model_years": "(2025,2030,2035,2040,2045,2050,2055)"}'
    ```
 
    Run a variation of that command. Note the single vs double quotes in this command. It needs to pass
    a valid JSON object to `dbt`.

    ```{eval-rst}
    .. code-block:: console

        $ dbt docs generate --vars '{"scenario": "baseline", "country": "country_1", "model_years": "(2025,2030,2035,2040,2045)"}'
    ```

4. Serve the documentation on a port on your local computer. This command should automatically open
your browser to a dbt-generated website at `http://localhost:8080`.

    ```{eval-rst}
    .. code-block:: console

        $ dbt docs serve
    ```

    This web UI shows information about the SQL queries that create all calculated tables. Here is how
    to navigate to the overall workflow graph for `energy_projection`.

    - On the upper left you will see `Projects` and `stride`.
    - Click `stride` and then `models` will appear. Click it.
    - All calculated tables will appear. Click `energy_projection`.
    - Click the graph-like icon on the bottom right with the title `View Lineage Graph`.
    - Click the square on the top right. It will display `View Fullscreen` when you hover over it.
