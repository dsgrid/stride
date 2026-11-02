(core-concepts)=
(explanation)=
# Core Concepts

These pages explain the data and computations behind a STRIDE projection. They follow the rough flow of a project: input datasets are sourced, downloaded, and validated, then transformed by dbt into hourly load forecasts that reflect historical weather.

```{toctree}
:maxdepth: 2
:caption: Input data

global_dataset_data_sources
data_download
data_validation
customizing_checks
```

```{toctree}
:maxdepth: 2
:caption: Computation

dbt_computation
weather_year_modeling
```
