(launch-dashboard)=
# Launch the Dashboard

View project results interactively in a web browser.

## Start the Dashboard

```{eval-rst}

.. code-block:: console

   $ stride view my_project

   Dash is running on http://127.0.0.1:8050/

   * Serving Flask app 'STRIDE'
   * Debug mode: off
   WARNING: This is a development server. Do not use it in a production deployment. Use a production WSGI server instead.
   * Running on http://127.0.0.1:8050
   Press CTRL+C to quit   
```

then CTRL-click on or copy-paste the address into your browser.

This opens an interactive dashboard where you can:

- Compare and browse scenarios
- Compare results across years, sectors, and end uses
- View, customize, and export pre-populated visualizations (e.g., bar chart, load duration curve, timeseries, summary statistics)

## Specify a Port

```{eval-rst}

.. code-block:: console

   $ stride view my_project --port 8080
```

## View Without a Project

Launch the dashboard without a project:

```{eval-rst}

.. code-block:: console

   $ stride view
```

Projects can be loaded and color palettes can be managed from the sidebar.
