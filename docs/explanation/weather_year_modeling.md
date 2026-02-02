(weather-year-modeling)=
# Weather Year Modeling

STRIDE uses detailed weather data to adjust electricity load shapes for temperature variations throughout the year. This page explains how weather data are processed and applied to create realistic hourly load profiles.

## Overview

Weather-based load adjustments follow this workflow:

```
Weather BAIT Data
    ↓
Degree Day Calculation (HDD/CDD)
    ↓
Shoulder Month Smoothing (Adjusted HDD/CDD)
    ↓
Temperature Multipliers
    ↓
Load Shape Expansion (Representative → Full Year)
    ↓
Annual Energy Scaling
    ↓
Final Hourly Load Shapes
```

## Input weather data

STRIDE uses Building-Adjusted Integrated Temperature (BAIT) data derived from ERA5 reanalysis weather data. BAIT is a composite temperature metric that accounts for:
- Outdoor dry-bulb temperature
- Surface solar radiation
- Wind speed at 2m
- Humidity
- Building thermal characteristics

The calculation methodology is similar to that described in Staffell, Pfenninger, and Johnson (2023).[^1]

The weather data includes:
- **Temporal resolution**: Daily (averaged from hourly ERA5 data)
- **Coverage**: Weather years 1995-2024
- **Geographic representation**: Country-level, based on a single highly or most-populous location per country
- **Variables**: Temperature, Solar Radiation, Wind Speed, Dew Point, Humidity, BAIT

[^1]: Staffell, I., Pfenninger, S., & Johnson, N. (2023). A global model of hourly space heating and cooling demand at multiple spatial scales. *Nature Energy*, 8, 1328-1344. https://doi.org/10.1038/s41560-023-01341-5

[^2]: Castillo, R., van Ruijven, B.J., Pfenninger, S., van Vuuren, D.P., Carrara, S., & Patel, M.K. (2022). Future global electricity demand load curves. *Energy*, 259, 124857. https://doi.org/10.1016/j.energy.2022.124857

## Degree day calculation

### Heating and cooling degree days

Degree days quantify how much heating or cooling is needed on a given day:

**Heating Degree Days (HDD)**:
```sql
HDD = GREATEST(0, heating_threshold - BAIT)
```

**Cooling Degree Days (CDD)**:
```sql
CDD = GREATEST(0, BAIT - cooling_threshold)
```

### ModelParameters

These thresholds are configurable through `ModelParameters`:

| Parameter | Description | Default | Unit |
|-----------|-------------|---------|------|
| `heating_threshold` | Temperature below which heating is needed | 18.0 | °C |
| `cooling_threshold` | Temperature above which cooling is needed | 18.0 | °C |

Example configuration in `project.json5`:

```json5
{
  project_id: "my_project",
  // ... other config ...
  model_parameters: {
    heating_threshold: 18.0,
    cooling_threshold: 18.0,
  }
}
```

### Degree day grouping

Degree days are aggregated by:
- **Geography**: Country or region
- **Weather Year**: Reference year for weather patterns
- **Month**: Calendar month (1-12)
- **Day Type**: Weekday or weekend

This grouping enables:
- Seasonal variation analysis
- Weekday/weekend pattern differences
- Representative day selection

## Temperature multiplier calculation

Temperature multipliers scale representative day heating/cooling load across days within each group (month + day type) based on relative temperature extremes.

### Basic multiplier formula

For a day with HDD value in a month with total HDD:

```
heating_multiplier = (HDD / total_HDD) × num_days
```

Similarly for cooling:

```
cooling_multiplier = (CDD / total_CDD) × num_days
```

**Key property**: Multipliers sum to `num_days` within each group, preserving total energy.

### The shoulder month problem

In spring and fall ("shoulder months"), some days may have zero or very low degree days while others have significant heating or cooling needs. Without adjustment, this creates unrealistic load spikes by concentrating all HVAC load on just the extreme days.

Example shoulder month (April):
- Days 1-21, 27-30: HDD = 0 (mild weather)
- Days 22-26: HDD = 5-10 (cold snap)

Without smoothing, all heating load would be assigned to days 22-26, creating artificial spikes.

### Shoulder month smoothing

STRIDE applies a minimum threshold to smooth these transitions:

```sql
-- Calculate maximum degree days in each group
max_hdd = MAX(hdd) in (month, day_type)
min_threshold = max_hdd / shoulder_month_smoothing_factor

-- Apply threshold
adjusted_hdd = CASE
    WHEN hdd < min_threshold THEN min_threshold
    ELSE hdd
END
```

This ensures all days in shoulder months experience some HVAC load, preventing unrealistic concentration.

### Smoothing parameters

| Parameter | Description | Default | Typical Values |
|-----------|-------------|---------|----------------|
| `enable_shoulder_month_smoothing` | Enable/disable smoothing | `true` | `true`/`false` |
| `shoulder_month_smoothing_factor` | Divisor for max degree days | 10.0 | 5.0 (aggressive), 10.0 (moderate), 20.0 (gentle) |

Example in `project.json5`:

```json5
{
  project_id: "my_project",
  // ... other config ...
  model_parameters: {
    enable_shoulder_month_smoothing: true,
    shoulder_month_smoothing_factor: 10.0,  // Moderate smoothing
  }
}
```

**Effect of smoothing factor**:
- **Lower values (5)**: More aggressive smoothing, broader load distribution
- **Higher values (20)**: Gentler smoothing, closer to original pattern
- **Disabled**: No smoothing, potential for unrealistic spikes

### Adjusted multiplier calculation

Final multipliers use adjusted degree days:

```
heating_multiplier = (adjusted_hdd / adjusted_total_hdd) × num_days
```

```
cooling_multiplier = (adjusted_cdd / adjusted_total_cdd) × num_days
```

This preserves energy conservation (multipliers still sum to `num_days`) while smoothing shoulder month transitions.

## Application to load shapes

### Load shapes for representative days

Load shapes from the IMAGE Integrated Assessment Model (Castillo et al. 2022)[^2] provide hourly consumption profiles. The dataset includes:
- **One weekday and one weekend day per month** (24 total representative days)
- **24 hourly values per day** (e.g., hour 0 = midnight-1am, hour 23 = 11pm-midnight)
- **Segmentation by**: End use (Heating, Cooling, Other), sector (Residential, Commercial, Industrial, Transportation), geography, model year

### Expansion to full year

The `load_shapes_expanded` dbt model expands these 24 representative days into 8760 hours (365 days × 24 hours) by:

1. **Matching each calendar day** of the selected weather year to its representative profile:
   - Days are matched by month (January → January representative day) and day type (weekday/weekend)
   - Example: Tuesday, January 15 uses the January weekday profile
   
2. **Applying temperature multipliers** to adjust for weather:
   ```sql
   adjusted_value = load_shape_value * multiplier
   
   -- Multiplier depends on end use:
   multiplier = CASE
       WHEN enduse = 'heating' THEN heating_multiplier
       WHEN enduse = 'cooling' THEN cooling_multiplier
       ELSE 1.0  -- Non-HVAC end uses (lighting, equipment, etc.)
   END
   ```

3. **Repeating the 24-hour pattern** for each day with its specific temperature multiplier

**Result**: Full-year hourly load shapes that preserve:
- Original hourly patterns from IMAGE (morning/evening peaks, daily cycles)
- Monthly seasonal variation (via representative days)
- Weekday/weekend differences
- Historical weather patterns (via weather-driven adjustments for heating/cooling end uses based on ERA5)

## Scaling to annual consumption

The final step scales weather-adjusted hourly shapes to match annual energy projections.

### Annual energy projection

For each sector/subsector/model year, STRIDE calculates annual energy demand from:
- Energy intensity regressions (energy per unit GDP, or population x HDI)
- Energy use driver projections (GDP, HDI, population)

This produces annual totals in MWh for each sector.

### Scaling factor calculation

```python
# Sum all hourly values for the year
load_shape_annual_total = SUM(expanded_hourly_values)

# Calculate scaling factor
scaling_factor = projected_annual_energy / load_shape_annual_total
```

### Final hourly values

```python
final_hourly_load = expanded_hourly_value * scaling_factor
```

This ensures:
- Hourly values sum to the projected annual total
- Weather-based daily/seasonal patterns are preserved
- Realistic load profiles throughout the year

## dbt models

The weather year modeling pipeline is implemented in these dbt models:

| Model | Purpose |
|-------|---------|
| `weather_bait_daily` | Pivots weather data from long to wide format and extracts date components |
| `weather_degree_days` | Calculates daily HDD and CDD from BAIT |
| `weather_degree_days_grouped` | Aggregates degree days by geography, weather year, month, and day type |
| `temperature_multipliers` | Computes daily multipliers with shoulder month smoothing |
| `load_shapes_expanded` | Applies temperature multipliers to expand representative days to full year |
| `energy_projection_*` | Combines expanded load shapes with energy intensity to produce projections |

## Logging and diagnostics

When computing energy projections, STRIDE logs temperature multiplier statistics:

```
INFO: Computing energy projection with model parameters: 
      heating_threshold=18.0, cooling_threshold=18.0, 
      enable_shoulder_month_smoothing=True, shoulder_month_smoothing_factor=10.0
INFO: Running scenario=baseline with weather_year=2018, 
      shoulder_month_smoothing=enabled (factor=10.0)
INFO: Temperature multiplier ranges for scenario=baseline: 
      heating=[0.234, 3.456], cooling=[0.123, 4.567], other=[1.000, 1.000]
```

## Related Topics

- {ref}`dbt-computation` - Overall dbt transformation pipeline
- {ref}`create-project-tutorial` - Tutorial on creating a stride project
- {ref}`dbt-projet` - Tutorial on browsing the dbt portion of a stride project
- {ref}`data-api-tutorial` - Tutorial on accessing and processing result data using Python