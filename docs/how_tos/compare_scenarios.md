(compare-scenarios)=
# Compare Scenarios

Query and compare results across scenarios programmatically.

## Load the Project

```python
from stride import Project

with Project.load("my_project") as project:
    api = project.api
```

## Query Multiple Scenarios

```python
baseline = api.get_total_consumption(scenario="baseline")
high_growth = api.get_total_consumption(scenario="high_growth")
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
comparison["pct_change"] = (
    comparison["difference"] / comparison["value_baseline"] * 100
)
```

## Visualize the Comparison

```python
import plotly.express as px

fig = px.bar(
    comparison,
    x="model_year",
    y="pct_change",
    color="geography",
    title="Consumption Change: High Growth vs Baseline"
)
fig.show()
```

See the {ref}`data-api-tutorial` for more examples.
