# STRIDE documentation

STRIDE (Smart Trending and Resource Insights for Demand Estimation) is a Python tool for assembling annual hourly electricity demand projections suitable for grid planning at the country-level. STRIDE is designed to enable quick assembly of first-order load forecasts that can then be refined, guided by visual QA/QC of results. The first order load forecasts are based on country-level data describing normalized electricity use trends, electricity use correlates (e.g., population, human development index, gross domestic product), weather, and load shapes. Alternative scenarios and forecast refinements can be made by layering in user-supplied data at any point in the calculation workflow and/or opting to use more complex forecasting models for certain subsectors/end uses.

STRIDE currently supports load forecasting for 148 countries and allows users to select a more detailed forecasting methodology for light-duty passenger electric vehicles.

## How to use this guide

- {ref}`getting-started`: Install STRIDE and browse typical workflow steps.
- {ref}`core-concepts`: Learn about STRIDE's data pipeline and architecture.
- {ref}`how-tos`: Step-by-step instructions for common activities.
- {ref}`tutorials`: Examples of creating projects, exploring outputs, and debugging issues.
- {ref}`reference`: Python API and command line interface (CLI) documentation.

```{eval-rst}
.. toctree::
    :maxdepth: 2
    :caption: Contents:
    :hidden:

    explanation/index
    how_tos/index
    tutorials/index
    reference/index
```

## Indices and tables

- {ref}`genindex`
- {ref}`modindex`
- {ref}`search`

## Contact Us

If you have any comments or questions about STRIDE, please reach out to us at [dsgrid.info@nlr.gov](mailto:dsgrid.info@nlr.gov).
