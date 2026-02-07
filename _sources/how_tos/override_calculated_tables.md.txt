(override-calculated-tables)=
# Override Calculated Tables

Replace a calculated table with your own data.

## List Available Tables

```{eval-rst}

.. code-block:: console

   $ stride calculated-tables list my_project
```

## Override a Table

Provide a CSV file with the same columns as the original table:

```{eval-rst}

.. code-block:: console

   $ stride calculated-tables override my_project gdp_country custom_gdp_country.csv
```

The CSV must match the table's schema (geography, model_year, and value columns).

## Remove an Override

Restore the original calculated table:

```{eval-rst}

.. code-block:: console

   $ stride calculated-tables remove-override my_project gdp_country
```

## View Current Data

Check the table contents after overriding:

```{eval-rst}

.. code-block:: console

   $ stride calculated-tables show my_project gdp_country
```
