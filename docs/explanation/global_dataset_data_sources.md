(global-dataset-data-sources)=
# Global Dataset Data Sources

The default STRIDE `global` dataset is assembled from several public data products. This page summarizes which sources contribute to each part of the projection. For information on how these data are retrieved and compiled, see {ref}`data-download` and {ref}`data-validation`.

## Default Projection

These sources are combined to estimate annual electricity consumption per country and sector:

- [IEA World Energy Balances](https://www.iea.org/data-and-statistics/data-product/world-energy-balances) -- Historic data on energy use are combined with the below datasets to estimate energy intensity, which is then summarized and projected per-country, per-sector log-linear or linear regressions.
- [2024 World Economic League Table](https://www.imf.org/en/Publications/WEO/weo-database/2024/October/weo-report) -- Historical GDP from the 2024 IMF World Economic Outlook (WEO) and GDP forecasts from the Centre for Economics and Business Research (CEBR).
- [United Nations World Population Prospects](https://population.un.org/wpp/) -- Historical and median projected population data
- [United Nations Development Reports](https://hdr.undp.org/data-center/human-development-index#/indicies/HDI) -– Historical human development index (HDI) data projected to 2050 with per-country logistic regressions.

## Electric Vehicle Projection

STRIDE includes an optional, more detailed projection for light-duty passenger electric vehicles (EVs) that replaces the default transportation on-road forecast when `use_ev_projection` is enabled. These sources supply information on current and projected EV stock shares, per-capita vehicle ownership, per-vehicle annual use, and EV energy intensity:

- [IEA Global EV Outlook](https://www.iea.org/reports/global-ev-outlook-2025) –- Historical EV stock and stock shares broken out by vehicle type (e.g., Cars, Vans, Trucks) and powertrain (i.e., BEV, PHEV) by country and year
- [OECD Road motor vehicle traffic dataset](https://data-explorer.oecd.org/) –- Historical total on-road vehicle kilometers by country and year
- [BNEF Electric Vehicle Outlook 2025](https://about.bnef.com/insights/clean-transport/electric-vehicle-outlook/) –- EV stock projections for select countries and regions used to create prototypical (logistic) adoption shapes that are then customized per country based on historic EV stock shares from the IEA Global EV Outlook
- [NREL 2024 Annual Technology Baseline (ATB) for Transportation](https://atb.nrel.gov/transportation/2024/index) –- Default energy use per kilometer and PHEV utility factor projections.[^atb]

[^atb]: STRIDE currently uses the Mid scenario, Midsize car values, linearly interpolated, for all countries. BEV assumptions are taken from "Battery Electric Vehicle (300-mile range)" and PHEV assumptions from "Gasoline Extended Range Plug-in Hybrid Electric Vehicle (35-mile electric range)".

## Profile Data

These sources shape the annual projections from the prior sections into hourly load forecasts, capturing typical diurnal and weekday/weekend patterns by sector and end use and day-to-day variations driven by historical weather:

- [IMAGE Integrated Assessment Model](https://data.mendeley.com/datasets/pmd2dchk44/1) – Modeled load shapes by sector and end use by country, month, day type (weekday/weekend) and model year (1971 – 2100)
- [ERA5](https://cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels?tab=overview) + [Demand Ninja Logic](https://doi.org/10.1038/s41560-023-01341-5) – Building-adjusted internal temperature (BAIT) and other weather variables for a representative location per country. Daily averages for historical weather years, currently 1995-2024. Can be computed for any years 1940 – present day.

## Related Topics

- {ref}`data-download` - How datasets are retrieved and stored locally
- {ref}`data-validation` - How datasets are validated and registered with dsgrid
- {ref}`weather-year-modeling` - How weather data are used to shape hourly load
