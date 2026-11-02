(core-concepts)=
(explanation)=
# Core Concepts

These pages explain the data and computations behind a STRIDE projection. They follow the rough flow of a project: input datasets are sourced, downloaded, and validated, then transformed by dbt into hourly load forecasts that reflect historical weather.

## Input Data

```{toctree}
:maxdepth: 1

data_download
global_dataset_data_sources
data_validation
customizing_checks
```

## Computation

```{toctree}
:maxdepth: 1

dbt_computation
weather_year_modeling
time_conventions
```
