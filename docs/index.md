# STRIDE documentation

STRIDE (Smart Trending and Resource Insights for Demand Estimation) is a Python tool for assembling annual hourly electricity demand projections suitable for grid planning at the country-level. STRIDE is designed to enable quick assembly of first-order load forecasts that can then be refined, guided by visual QA/QC of results. The first order load forecasts are based on country-level data describing normalized electricity use trends, electricity use correlates (e.g., population, human development index, gross domestic product), weather, and load shapes. Alternative scenarios and forecast refinements can be made by layering in user-supplied data at any point in the calculation workflow and/or opting to use more complex forecasting models for certain subsectors/end uses.

STRIDE currently supports load forecasting for 148 countries and allows users to select a more detailed forecasting methodology for light-duty passenger electric vehicles.

## How to use this guide

- Refer to {ref}`core-concepts` for details on STRIDE's data pipeline and architecture.
- Refer to {ref}`getting-started` for installation and configuration details.
- Refer to {ref}`how-tos` for step-by-step instructions for common activities.
- Refer to {ref}`tutorials` for examples of creating a project and viewing energy projections.
- Refer to {ref}`reference` for API documentation and CLI reference documentation.

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
