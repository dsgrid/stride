(data-api-tutorial)=

# Process results with Python

This tutorial demonstrates how to use the STRIDE Data API to query and analyze
energy projection data programmatically.

For complete API documentation, see the {ref}`data-api-reference`.

## Prerequisites

- A STRIDE project created using `stride projects create`
- Python environment with STRIDE installed

## Load a project

First, load your project and create an API client:

```python
from stride.project import Project
from stride.api import APIClient

# Load an existing project
project = Project.load("my_project_path")

# Create an API client
client = APIClient(project)
```

## Explore available data

The API client provides methods to discover what data is available:

```python
# Get available scenarios
scenarios = client.scenarios
print(f"Scenarios: {scenarios}")

# Get available model years
years = client.get_years()
print(f"Model years: {years}")

# Get unique sectors and end uses
sectors = client.get_unique_sectors()
end_uses = client.get_unique_end_uses()
print(f"Sectors: {sectors}")
print(f"End uses: {end_uses}")
```

## Query annual consumption

Get total annual electricity consumption across scenarios:

```python
# Get total consumption for all scenarios and years
df = client.get_annual_electricity_consumption()
print(df)

# Filter to specific scenarios and years
df = client.get_annual_electricity_consumption(
    scenarios=["baseline", "ev_projection"],
    years=[2030, 2040, 2050]
)

# Break down by sector
df = client.get_annual_electricity_consumption(
    scenarios=["baseline"],
    group_by="Sector"
)
print(df)
```

Example output:

```
   scenario  year       sector         value
0  baseline  2025   Commercial  1.234567e+09
1  baseline  2025   Industrial  2.345678e+09
2  baseline  2025  Residential  1.876543e+09
3  baseline  2030   Commercial  1.345678e+09
...
```

## Query peak demand

Get annual peak demand values:

```python
# Get peak demand for all scenarios
df = client.get_annual_peak_demand()
print(df)

# Peak demand broken down by sector at the peak hour
df = client.get_annual_peak_demand(
    scenarios=["baseline"],
    years=[2030],
    group_by="Sector"
)
```

## Load duration curves

Generate load duration curves for capacity planning:

```python
# Load duration curve for a single year, comparing scenarios
df = client.get_load_duration_curve(
    years=2030,
    scenarios=["baseline", "ev_projection"]
)
print(df.head())

# Load duration curve comparing multiple years for one scenario
df = client.get_load_duration_curve(
    years=[2030, 2040, 2050],
    scenarios=["baseline"]
)
```

The result has hours sorted from highest to lowest demand:

```
        baseline  ev_projection
0    12500000.0     13200000.0
1    12450000.0     13150000.0
2    12400000.0     13100000.0
...
8759  3200000.0      3400000.0
```

## Time series comparison

Compare time series across model years:

```python
# Daily mean consumption for multiple years
df = client.get_time_series_comparison(
    scenario="baseline",
    years=[2030, 2050],
    resample="Daily Mean"
)
print(df.head())

# Weekly mean with sector breakdown
df = client.get_time_series_comparison(
    scenario="baseline",
    years=[2030],
    group_by="Sector",
    resample="Weekly Mean"
)
```

## Seasonal load patterns

Analyze load patterns by season and day type:

```python
# Average daily load profile by season
df = client.get_seasonal_load_lines(
    scenario="baseline",
    years=[2030],
    group_by="Seasonal",
    agg="Average Day"
)
print(df.head())

# Seasonal patterns split by weekday/weekend
df = client.get_seasonal_load_lines(
    scenario="baseline",
    years=[2030],
    group_by="Seasonal and Weekday/Weekend",
    agg="Average Day"
)
```

## Secondary metrics

Query economic and demographic data:

```python
# Get GDP data
gdp = client.get_secondary_metric(
    scenario="baseline",
    metric="GDP",
    years=[2030, 2040, 2050]
)
print(gdp)

# Get population data
population = client.get_secondary_metric(
    scenario="baseline",
    metric="Population"
)

# GDP per capita (calculated automatically)
gdp_per_capita = client.get_secondary_metric(
    scenario="baseline",
    metric="GDP Per Capita"
)
```

## Weather data

Query weather metrics for analysis:

```python
# Get daily mean temperature (BAIT)
weather = client.get_weather_metric(
    scenario="baseline",
    year=2030,
    wvar="BAIT",
    resample="Daily Mean"
)
print(weather.head())

# Heating and cooling degree days
hdd = client.get_weather_metric(
    scenario="baseline",
    year=2030,
    wvar="HDD",
    resample="Daily Mean"
)
```

## Create visualizations

Use the queried data with plotly for interactive visualizations:

```python
import plotly.express as px

# Plot annual consumption by scenario
df = client.get_annual_electricity_consumption()
fig = px.bar(
    df,
    x="year",
    y="value",
    color="scenario",
    barmode="group",
    title="Annual Electricity Consumption by Scenario",
    labels={"value": "Consumption (MWh)", "year": "Year", "scenario": "Scenario"}
)
fig.write_html("consumption_by_scenario.html")
fig.show()
```

```python
import plotly.graph_objects as go

# Plot load duration curves
ldc = client.get_load_duration_curve(years=2030, scenarios=["baseline", "ev_projection"])

fig = go.Figure()
for col in ldc.columns:
    fig.add_trace(go.Scatter(
        x=list(range(len(ldc))),
        y=ldc[col],
        mode="lines",
        name=col
    ))

fig.update_layout(
    title="Load Duration Curve - 2030",
    xaxis_title="Hours",
    yaxis_title="Demand (MW)",
    legend_title="Scenario"
)
fig.write_html("load_duration_curve.html")
fig.show()
```

```python
# Plot seasonal load profiles
seasonal = client.get_seasonal_load_lines(
    scenario="baseline",
    years=[2030],
    group_by="Seasonal"
)

fig = px.line(
    seasonal,
    x="hour_of_day",
    y="value",
    color="season",
    title="Average Daily Load Profile by Season - 2030",
    labels={"hour_of_day": "Hour of Day", "value": "Load (MW)", "season": "Season"}
)
fig.write_html("seasonal_profiles.html")
fig.show()
```

```python
# Plot consumption breakdown by sector as stacked area
df = client.get_annual_electricity_consumption(
    scenarios=["baseline"],
    group_by="Sector"
)

fig = px.area(
    df,
    x="year",
    y="value",
    color="sector",
    title="Annual Consumption by Sector - Baseline",
    labels={"value": "Consumption (MWh)", "year": "Year", "sector": "Sector"}
)
fig.write_html("consumption_by_sector.html")
fig.show()
```

## Export to CSV or Excel

Save results for use in other tools:

```python
# Export consumption data to CSV
df = client.get_annual_electricity_consumption(group_by="Sector")
df.to_csv("consumption_by_sector.csv", index=False)

# Export to Excel with multiple sheets
with pd.ExcelWriter("stride_results.xlsx") as writer:
    consumption = client.get_annual_electricity_consumption()
    consumption.to_excel(writer, sheet_name="Consumption", index=False)

    peak = client.get_annual_peak_demand()
    peak.to_excel(writer, sheet_name="Peak Demand", index=False)

    ldc = client.get_load_duration_curve(years=2030)
    ldc.to_excel(writer, sheet_name="Load Duration", index=False)
```

## Complete example

Here's a complete script that generates a summary report:

```python
from stride.project import Project
from stride.api import APIClient

# Use context manager to automatically close the project
with Project.load("my_project_path") as project:
    client = APIClient(project)

    # Print project info
    print(f"Project: {project.config.project_id}")
    print(f"Country: {project.config.country}")
    print(f"Scenarios: {client.scenarios}")
    print(f"Years: {client.get_years()}")
    print()

    # Summary statistics
    for scenario in client.scenarios:
        print(f"=== {scenario} ===")

        consumption = client.get_annual_electricity_consumption(scenarios=[scenario])
        peak = client.get_annual_peak_demand(scenarios=[scenario])

        for year in client.get_years():
            cons_val = consumption[consumption["year"] == year]["value"].values[0]
            peak_val = peak[peak["year"] == year]["value"].values[0]

            print(f"  {year}: {cons_val/1e9:.2f} TWh, Peak: {peak_val/1e6:.2f} GW")
        print()
```
