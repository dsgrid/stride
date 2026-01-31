(dbt-computation)=
# dbt Computation

STRIDE uses [dbt (data build tool)](https://www.getdbt.com/) to transform validated input data into energy projections. dbt provides a SQL-based workflow for defining and executing data transformations.

## Why dbt?

dbt offers several advantages for STRIDE's computation pipeline:

- **SQL-based** - Transformations are expressed in familiar SQL
- **Modular** - Models can be composed and reused
- **Documented** - Built-in support for model documentation
- **Testable** - Define tests for data quality
- **Incremental** - Only recompute what's changed

## Project Structure

Each STRIDE project includes a dbt project in the `dbt/` directory:

```
<project>/dbt/
├── dbt_project.yml          # dbt project configuration
├── profiles.yml             # Database connection settings
├── models/                  # SQL transformation models
│   ├── sources.yml          # Source table definitions
│   ├── energy_intensity_*.sql
│   ├── load_shapes_*.sql
│   ├── energy_projection.sql
│   └── ev_*.sql             # Electric vehicle models
├── macros/                  # Reusable SQL macros
│   ├── table_ref.sql        # Override reference macro
│   └── get_custom_schema.sql
└── target/                  # Compiled output (generated)
```

## How dbt is Invoked

When you create a project or call `compute_energy_projection()`, STRIDE runs dbt for each scenario:

```python
dbt run --vars '{"scenario": "baseline", "country": "USA", ...}'
```

### Variables Passed to dbt

Each dbt run receives these variables:

| Variable | Description | Example |
|----------|-------------|---------|
| `scenario` | Scenario name | `"baseline"` |
| `country` | Country identifier | `"USA"` |
| `model_years` | Years to compute | `"(2025,2030,2035)"` |
| `weather_year` | Reference weather year | `2019` |
| `heating_threshold` | Temperature for heating loads | `18` |
| `cooling_threshold` | Temperature for cooling loads | `18` |
| `use_ev_projection` | Enable EV calculations | `true` |

## Data Flow

The computation follows this flow:

```
Input Tables (dsgrid_data schema)
    ↓
dbt Models (SQL transformations)
    ↓
Scenario Tables ({scenario} schema)
    ↓
Combined energy_projection table
```

### Input Tables

dbt reads from tables in the `dsgrid_data` schema:

- `energy_intensity` - Regression parameters for energy intensity
- `gdp` - Gross domestic product projections
- `hdi` - Human development index
- `population` - Population projections
- `load_shapes` - Hourly load profiles
- `weather_bait` - Building-adjusted temperatures

### Transformation Models

Key transformations include:

1. **Energy Intensity Parsing** - Extract regression parameters from source data
2. **Driver Combination** - Join intensity coefficients with GDP, HDI, population
3. **Regression Application** - Apply exponential/linear regression formulas
4. **Load Shape Scaling** - Scale hourly profiles to match annual projections
5. **Final Aggregation** - Combine all sectors into the final projection

### Output Tables

Each scenario produces tables in its own schema:

```sql
baseline.energy_projection
baseline.energy_intensity_parsed
baseline.load_shapes_scaled
...
```

All scenarios are then combined into the main `energy_projection` table.

## The Override Mechanism

STRIDE supports overriding calculated tables at any point in the pipeline. This is implemented through the `table_ref` macro:

```sql+jinja
-- In a dbt model
SELECT * FROM {{ table_ref('energy_intensity_parsed') }}
```

The macro checks if an override variable exists:

- If override exists: use the override table
- If no override: use the default table

This allows you to inject custom data at any transformation step without modifying the SQL models.

## Debugging dbt

### View Compiled SQL

After running, compiled SQL is available in:

```
<project>/dbt/target/compiled/stride/models/
```

### Check Logs

dbt logs are written to:

```
<project>/stride.log
```

### Run dbt Manually

You can run dbt directly for debugging:

```bash
cd <project>/dbt
dbt run --vars '{"scenario": "baseline", "country": "USA", "model_years": "(2025,2030)", "weather_year": 2019, "heating_threshold": 18, "cooling_threshold": 18, "use_ev_projection": false}'
```

## Customizing Calculations

### Override a Calculated Table

To replace a table with custom data:

```python
from stride.models import CalculatedTableOverride

project.override_calculated_tables([
    CalculatedTableOverride(
        scenario="baseline",
        table_name="energy_intensity_parsed",
        filename="my_custom_intensity.parquet",
    )
])
```

### Modify dbt Models

For advanced customization, you can edit the SQL models directly:

1. Navigate to `<project>/dbt/models/`
2. Edit the relevant `.sql` file
3. Run `project.compute_energy_projection()` to regenerate

## Related Topics

- {ref}`data-validation` - How input data is validated before dbt runs
- {ref}`customizing-checks` - Configuring validation behavior
