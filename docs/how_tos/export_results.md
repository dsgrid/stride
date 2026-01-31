(export-results)=
# Export Results

Export project data for external analysis.

## Export All Project Data

Export all scenarios and tables to Parquet files:

```{eval-rst}

.. code-block:: console

   $ stride projects export my_project ./output
```

## Export to CSV

Use the ``--format`` option:

```{eval-rst}

.. code-block:: console

   $ stride projects export my_project ./output --format csv
```

## Export a Single Calculated Table

Export a specific table:

```{eval-rst}

.. code-block:: console

   $ stride calculated-tables export my_project gdp ./gdp_data.parquet
```

Or as CSV:

```{eval-rst}

.. code-block:: console

   $ stride calculated-tables export my_project gdp ./gdp_data.csv --format csv
```
