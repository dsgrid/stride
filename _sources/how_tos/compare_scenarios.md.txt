(compare-scenarios)=
# Compare Scenarios

Programmatically query and compare results across scenarios.

## Load the Project

```python
from stride import Project
from stride.api import APIClient

project = Project.load("my_project")
client = APIClient(project)
```

## Query Multiple Scenarios

```python
baseline = client.get_annual_electricity_consumption(scenarios=["baseline"])
high_growth = client.get_annual_electricity_consumption(scenarios=["high_growth"])
```

## Calculate Differences

```python
import pandas as pd

comparison = pd.merge(
    baseline, high_growth,
    on=["year"],
    suffixes=("_baseline", "_high_growth")
)
comparison["difference"] = (
    comparison["value_high_growth"] - comparison["value_baseline"]
)
comparison["pct_difference"] = (
    comparison["difference"] / comparison["value_baseline"] * 100
)
```

## Visualize the Comparison

```python
import plotly.express as px

fig = px.scatter(
    comparison,
    x="year",
    y="pct_difference",
    title="Consumption Change: High Growth vs Baseline"
)
fig.show()
```

## See also

- {ref}`data-api-tutorial` for more examples.
- {ref}`launch-dashboard` for the visualization UI.
