(export-results)=
# Export Results

Export project data for external analysis.

## Export the Final Result Table

Export the final annual hourly energy projection for all scenarios to csv:

```{eval-rst}

.. code-block:: console

   $ stride projects export-energy-projection my_project

   INFO: Exported the energy projection table to energy_projection.csv
```

Export to .parquet:

```{eval-rst}

.. code-block:: console

   $ mkdir output
   $ stride projects export-energy-projection my_project --filename=output/energy_projection.parquet

   INFO: Exported the energy projection table to output\energy_projection.parquet
```

```{note}
CSV files contain timestamps in the project's time zone (the country's standard time, no
daylight saving time) with an explicit UTC offset, e.g., `2018-01-01 00:00:00+01`. Parquet files
store each timestamp as a UTC instant, which most tools read back in UTC or in your computer's
time zone; use the `time_zone` column to convert to local standard time. See
{ref}`time-conventions`.
```

## Export a Single Calculated Table

Export a specific table:

```{eval-rst}

.. code-block:: console

   $ stride calculated-tables export my_project --scenario=ev_projection --table-name=ev_stock_share_country

   INFO: Exported scenario=ev_projection table=ev_stock_share_country to ev_stock_share_country.csv
```

Export as .parquet:

```{eval-rst}

.. code-block:: console

   $ stride calculated-tables export my_project --scenario=baseline --table-name=weather_bait_daily --filename=weather_bait_daily.parquet

   INFO: Exported scenario=baseline table=weather_bait_daily to weather_bait_daily.parquet
```

Export in order to override in an existing or new scenario:

```{eval-rst}

.. code-block:: console

   $ stride calculated-tables export my_project --scenario=ev_projection --table-name=ev_stock_share_country

   INFO: Exported scenario=ev_projection table=phev_share_country to phev_share_country__revised.csv
```

## See also

- {ref}`data-api-tutorial` to customize output data and/or integrated into automated workflows
- {ref}`manage-calculated-tables` to browse and override calculated tables
- {ref}`dbt-projet` to see how the calculated tables relate to one another
