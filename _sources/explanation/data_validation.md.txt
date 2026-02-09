(data-validation)=
# Data Validation with dsgrid

STRIDE uses [dsgrid](https://github.com/dsgrid/dsgrid) to validate and register datasets. This ensures data consistency across dimensions like time, geography, and sector before computing energy projections.

## What is dsgrid?

dsgrid is a framework for managing demand-side grid data. STRIDE leverages dsgrid's registry system to:

- **Validate dimensions** - Ensure datasets have consistent time periods, geographies, and sectors
- **Map dimensions** - Transform dataset dimensions to match project requirements
- **Query data** - Extract and combine data from multiple registered datasets

## The Validation Process

When you create a STRIDE project, the following validation steps occur:

### 1. Registry Creation

STRIDE creates a local dsgrid registry backed by DuckDB:

```
<project>/registry_data/data.duckdb
```

This registry stores metadata about registered datasets and their dimensions.

### 2. Bulk Registration

Datasets from the data directory are registered with dsgrid using bulk registration. This process:

- Parses dataset configurations
- Validates dimension consistency
- Records dimension mappings

### 3. Dimension Mapping

STRIDE reads `dimension_mappings.json5` from the dataset directory to understand how to map dimensions between datasets. Common mapping types include:

- **many_to_one_aggregation** - Combine multiple source values into one target value
- **one_to_one** - Direct mapping between source and target dimensions

### 4. Query and Table Creation

After validation, STRIDE queries the dsgrid registry and creates DuckDB tables for each dataset:

```
dsgrid_data.baseline__energy_intensity__1_0_0
dsgrid_data.baseline__gdp__1_0_0
dsgrid_data.baseline__load_shapes__1_0_0
...
```

## What Gets Validated

### Time Consistency

By default, STRIDE checks that time dimensions are consistent across datasets. This ensures:

- All datasets cover the same time periods
- Timestamps align properly for joining

### Dimension Associations

Optionally, STRIDE can validate that dimension associations are consistent. This checks that:

- Geographic identifiers match across datasets
- Sector definitions are compatible
- All required dimension combinations exist

## Validation Errors

If validation fails, you'll see errors indicating:

- **Missing dimensions** - A required dimension is not present in the dataset
- **Inconsistent time periods** - Datasets have mismatched time ranges
- **Invalid mappings** - Dimension mappings reference non-existent values

## Scenarios and Alternative Datasets

STRIDE supports multiple scenarios, each potentially using different input datasets:

```json5
{
  "scenarios": [
    {"name": "baseline"},
    {"name": "high_growth", "gdp": "path/to/alternative_gdp.parquet"}
  ]
}
```

When a scenario specifies an alternative dataset:

1. The alternative is registered as a separate dataset
2. A view is created pointing to the alternative data
3. dbt uses the scenario-specific data for calculations

For datasets not overridden in a scenario, STRIDE creates views pointing to the baseline data to avoid redundant processing.

## Related Topics

- {ref}`customizing-checks` - How to enable or disable specific validation checks
- {ref}`dbt-computation` - How validated data flows into dbt calculations
