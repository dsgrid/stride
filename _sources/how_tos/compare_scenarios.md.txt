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
baseline = client.get_total_consumption(scenario="baseline")
high_growth = client.get_total_consumption(scenario="high_growth")
```

## Calculate Differences

```python
import pandas as pd

comparison = pd.merge(
    baseline, high_growth,
    on=["geography", "model_year"],
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
    x="model_year",
    y="pct_change",
    color="geography",
    title="Consumption Change: High Growth vs Baseline"
)
fig.show()
```

## See also

- {ref}`data-api-tutorial` for more examples.
- {ref}`launch-dashboard` for the visualization UI.
