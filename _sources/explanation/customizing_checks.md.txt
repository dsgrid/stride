(customizing-checks)=
# Customizing Dataset Checks

STRIDE performs validation checks when registering datasets with dsgrid. These checks can be customized using environment variables or programmatically through the API.

## Available Checks

STRIDE supports the following dataset validation checks:

| Check | Environment Variable | Default | Description |
|-------|---------------------|---------|-------------|
| Time Consistency | `STRIDE_CHECK_TIME_CONSISTENCY` | `true` | Validates that time dimensions are consistent across datasets |
| Dimension Associations | `STRIDE_CHECK_DIMENSION_ASSOCIATIONS` | `false` | Validates that dimension associations (e.g., geography-sector combinations) are consistent |

## Using Environment Variables

The simplest way to customize checks is through environment variables:

```bash
# Disable time consistency checks (faster project creation)
export STRIDE_CHECK_TIME_CONSISTENCY=false
stride project create my_config.json5

# Enable dimension association checks (more thorough validation)
export STRIDE_CHECK_DIMENSION_ASSOCIATIONS=true
stride project create my_config.json5
```

Valid values for boolean environment variables:
- **True**: `true`, `True`, `TRUE`, `1`
- **False**: `false`, `False`, `FALSE`, `0`

## Programmatic Configuration

When using the Python API, you can pass custom requirements directly:

```python
from stride import Project
from dsgrid.dimension.base_models import DatasetDimensionRequirements

# Create custom validation requirements
requirements = DatasetDimensionRequirements(
    check_time_consistency=False,
    check_dimension_associations=True,
    require_all_dimension_types=False,
)

# Create project with custom requirements
project = Project.create(
    "my_config.json5",
    dataset_requirements=requirements,
)
```

## When to Customize Checks

### Disabling Time Consistency Checks

Consider disabling time consistency checks when:

- You're iterating quickly during development
- Your datasets intentionally have different time ranges
- You're working with incomplete data and plan to fill gaps later

```bash
STRIDE_CHECK_TIME_CONSISTENCY=false stride project create config.json5
```

### Enabling Dimension Association Checks

Consider enabling dimension association checks when:

- You need to ensure complete coverage of all geographic regions
- You're preparing data for production use
- You want to catch missing sector-geography combinations

```bash
STRIDE_CHECK_DIMENSION_ASSOCIATIONS=true stride project create config.json5
```

## Check Behavior

### Time Consistency (`check_time_consistency=true`)

When enabled, this check verifies:

- All datasets have compatible time periods
- Timestamps can be properly aligned for joins
- No gaps exist in required time series

If validation fails, you'll see an error indicating which datasets have mismatched time dimensions.

### Dimension Associations (`check_dimension_associations=true`)

When enabled, this check verifies:

- All expected dimension combinations exist
- No orphaned dimension values (e.g., a sector without any geographic data)
- Associations are complete across all datasets

This is a more expensive check and is disabled by default for performance.

## Performance Considerations

Validation checks add overhead to project creation:

| Configuration | Speed | Thoroughness |
|--------------|-------|--------------|
| Both disabled | Fastest | Minimal validation |
| Time only (default) | Fast | Catches common issues |
| Both enabled | Slower | Most thorough |

For development workflows, consider disabling checks to speed up iteration, then re-enable them before finalizing your project.

## Related Topics

- {ref}`data-validation` - Overview of the validation process
- {ref}`data-download` - How to download datasets
