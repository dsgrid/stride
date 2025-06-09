import plotly.graph_objects as go

categories = ["Category A", "Category B", "Category C"]
group1_values = [20, 35, 30]
group2_values = [25, 32, 28]

fig = go.Figure()

fig.add_trace(
    go.Bar(x=categories, y=group1_values, name="Group 1", marker_color="blue")
)

fig.add_trace(go.Bar(x=categories, y=group2_values, name="Group 2", marker_color="red"))

fig.update_layout(
    barmode="group",
    title="Grouped Bar Chart",
    xaxis_title="Categories",
    yaxis_title="Values",
)

fig.show()
