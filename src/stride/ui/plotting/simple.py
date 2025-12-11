from typing import TYPE_CHECKING

import pandas as pd
import plotly.graph_objects as go

from .utils import (
    DEFAULT_BAR_COLOR,
    TRANSPARENT,
    create_time_series_area_traces,
    create_time_series_line_traces,
    get_time_series_breakdown_info,
)

if TYPE_CHECKING:
    from stride.ui.color_manager import ColorManager


def grouped_single_bars(
    df: pd.DataFrame, group: str, color_generator: "ColorManager", use_color_manager: bool = True
) -> go.Figure:
    """
    Create a bar plot with 2 levels of x axis.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame with columns: year, value, and the group column
    group : str
        Column name to group bars by
    color_generator : Callable[[str], str]
        Color generator function
    use_color_manager : bool, optional
        Whether to use the color manager for bar colors, by default True

    Returns
    -------
    go.Figure
        Plotly figure with grouped bar chart
    """
    fig = go.Figure()

    df_grouped = df[group].unique()
    for group_value in df_grouped:
        df_subset = df[df[group] == group_value]

        color = DEFAULT_BAR_COLOR
        if use_color_manager:
            color = color_generator.get_color(str(group_value))

        fig.add_trace(
            go.Bar(
                x=df_subset["year"].astype(str),
                y=df_subset["value"],
                name=str(group_value),
                marker_color=color,
                showlegend=True,
            )
        )

    fig.update_layout(
        plot_bgcolor=TRANSPARENT,
        paper_bgcolor=TRANSPARENT,
        margin_b=0,
        margin_t=20,
        margin_l=20,
        margin_r=20,
        barmode="group",
    )

    return fig


def grouped_multi_bars(
    df: pd.DataFrame,
    color_generator: "ColorManager",
    x_group: str = "scenario",
    y_group: str = "end_use",
) -> go.Figure:
    """
    Create grouped and multi-level bar chart.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame with year, value, and grouping columns
    color_generator : Callable[[str], str]
        Color generator function
    x_group : str, optional
        Primary grouping column (creates offset groups), by default "scenario"
    y_group : str, optional
        Secondary grouping column (creates stacked bars), by default "end_use"

    Returns
    -------
    go.Figure
        Plotly figure with grouped multi-bars
    """
    bars = []

    # Get max value for indicator bar sizing
    max_value = df["value"].max()
    indicator_height = max_value * 0.02

    # Add data bars - group by sector for sector toggling
    # NOTE: Due to Plotly's legend system limitations, we can only toggle one dimension
    # independently. Data bars are grouped by sector/end_use so clicking a sector
    # toggles that sector across all scenarios. Scenario indicators are visual only.
    added_y_legend = set()
    y_group_title_added = False
    for y_value in sorted(df[y_group].unique()):
        for x_value in sorted(df[x_group].unique()):
            df_subset = df[(df[x_group] == x_value) & (df[y_group] == y_value)]
            bars.append(
                go.Bar(
                    x=df_subset["year"].astype(str),
                    y=df_subset["value"],
                    marker_color=color_generator.get_color(y_value),
                    name=y_value,
                    offsetgroup=x_value,
                    legendgroup=y_value,
                    legendgrouptitle_text=y_group.replace("_", " ").title()
                    if not y_group_title_added
                    else None,
                    legendrank=1,
                    showlegend=y_value not in added_y_legend,
                )
            )
            if not y_group_title_added:
                y_group_title_added = True
            added_y_legend.add(y_value)

    # Add colored indicator bars for scenarios (visual reference)
    # These appear in the legend but clicking them only toggles the indicator itself,
    # not the data bars. Use scenario selection checkboxes for full scenario toggling.
    years = sorted(df["year"].unique())
    scenario_title_added = False
    for i, x_value in enumerate(sorted(df[x_group].unique())):
        bars.append(
            go.Bar(
                x=[str(year) for year in years],
                y=[indicator_height] * len(years),
                name=x_value,
                legendgroup="scenarios",  # All scenarios share same legendgroup
                legendgrouptitle_text="Scenarios" if not scenario_title_added else None,
                legendrank=2,
                marker=dict(
                    color=color_generator.get_color(x_value),
                    pattern_shape="/",
                    pattern_solidity=0.3,
                ),
                offsetgroup=x_value,
                showlegend=True,
                base=-indicator_height * 2.5,
                hoverinfo="skip",
            )
        )
        if not scenario_title_added:
            scenario_title_added = True

    fig = go.Figure(data=bars)
    fig.update_layout(
        plot_bgcolor=TRANSPARENT,
        paper_bgcolor=TRANSPARENT,
        margin_b=0,
        margin_t=20,
        margin_l=20,
        margin_r=20,
        barmode="stack",
        yaxis=dict(range=[-indicator_height * 4, max_value * 1.1]),
        legend=dict(
            itemclick="toggle",  # Single click toggles sectors (or scenario indicators)
            itemdoubleclick=False,  # Disabled - can't handle 2D toggling properly
        ),
    )

    return fig


def grouped_stacked_bars(
    df: pd.DataFrame,
    color_generator: "ColorManager",
    year_col: str = "year",
    group_col: str = "scenario",
    stack_col: str = "metric",
    value_col: str = "demand",
) -> go.Figure:
    """
    Create grouped and stacked bar chart.

    Groups by year (x-axis positions), each group contains multiple bar stacks
    (one per scenario), and each stack is colored by sector/end_use.

    Parameters
    ----------
    df : pd.DataFrame
        Input data with required columns
    color_generator : Callable[[str], str]
        Color generator function
    year_col : str, optional
        Column name for years (x-axis), by default "year"
    group_col : str, optional
        Column name for grouping (creates separate stacks), by default "scenario"
    stack_col : str, optional
        Column name for stacking (colors within stacks), by default "metric"
    value_col : str, optional
        Column name for values (y-axis), by default "demand"

    Returns
    -------
    go.Figure
        Plotly figure with grouped stacked bars
    """
    fig = go.Figure()

    years = sorted(df[year_col].unique())
    groups = sorted(df[group_col].unique())
    stack_categories = sorted(df[stack_col].unique())

    # Get the maximum value to determine indicator bar height
    max_value = df[value_col].max()
    indicator_height = max_value * 0.02  # 2% of max value

    # Create data traces - group by sector for sector toggling
    # NOTE: Due to Plotly's legend system limitations, we can only toggle one dimension
    # independently. Data bars are grouped by sector/end_use so clicking a sector
    # toggles that sector across all scenarios. Scenario indicators are visual only.
    added_stack_legend = set()
    stack_group_title_added = False
    for stack_cat in stack_categories:
        for group in groups:
            df_subset = df[(df[group_col] == group) & (df[stack_col] == stack_cat)]

            fig.add_trace(
                go.Bar(
                    x=df_subset[year_col].astype(str),
                    y=df_subset[value_col],
                    name=stack_cat,
                    legendgroup=stack_cat,
                    legendgrouptitle_text=stack_col.replace("_", " ").title()
                    if not stack_group_title_added
                    else None,
                    marker_color=color_generator.get_color(stack_cat),
                    offsetgroup=group,
                    legendrank=1,
                    showlegend=stack_cat not in added_stack_legend,
                )
            )
            if not stack_group_title_added:
                stack_group_title_added = True
            added_stack_legend.add(stack_cat)

    # Add colored indicator bars for scenarios (visual reference)
    # These appear in the legend but clicking them only toggles the indicator itself,
    # not the data bars. Use scenario selection checkboxes for full scenario toggling.
    scenario_title_added = False
    for i, group in enumerate(groups):
        fig.add_trace(
            go.Bar(
                x=[str(year) for year in years],
                y=[indicator_height] * len(years),
                name=group,
                legendgroup="scenarios",  # All scenarios share same legendgroup
                legendgrouptitle_text="Scenarios" if not scenario_title_added else None,
                legendrank=2,
                marker=dict(
                    color=color_generator.get_color(group),
                    pattern_shape="/",
                    pattern_solidity=0.3,
                ),
                offsetgroup=group,
                showlegend=True,
                base=-indicator_height * 2.5,
                hoverinfo="skip",
            )
        )
        if not scenario_title_added:
            scenario_title_added = True

    fig.update_layout(
        plot_bgcolor=TRANSPARENT,
        paper_bgcolor=TRANSPARENT,
        margin_b=50,
        margin_t=20,
        margin_l=20,
        margin_r=20,
        barmode="stack",
        yaxis=dict(range=[-indicator_height * 4, max_value * 1.1]),
        legend=dict(
            itemclick="toggle",  # Single click toggles sectors (or scenario indicators)
            itemdoubleclick=False,  # Disabled - can't handle 2D toggling properly
        ),
    )

    return fig


def time_series(
    df: pd.DataFrame,
    color_generator: "ColorManager",
    group_by: str | None = None,
    chart_type: str = "Line",
) -> go.Figure:
    """
    Plot time series data for multiple years of a single scenario.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame with columns: scenario, year, time_period, value
        and optionally a breakdown column (sector/end_use)
    color_generator : Callable[[str], str]
        Color generator function
    group_by : str, optional
        Column name for breakdown grouping (e.g., "sector", "end_use")
    chart_type : str, optional
        "Line" or "Area" chart type, by default "Line"

    Returns
    -------
    go.Figure
        Plotly figure with time series lines or area chart
    """
    fig = go.Figure()

    # Get breakdown information
    breakdown_info = get_time_series_breakdown_info(df, group_by)

    # Handle invalid data format
    if breakdown_info.get("invalid", False):
        fig.add_annotation(
            text="Invalid data format",
            x=0.5,
            y=0.5,
            xref="paper",
            yref="paper",
            showarrow=False,
        )
    else:
        # Create traces based on chart type
        if chart_type == "Area":
            traces = create_time_series_area_traces(df, color_generator, breakdown_info)
        else:  # Line chart
            traces = create_time_series_line_traces(df, color_generator, breakdown_info)

        # Add all traces to figure
        for trace in traces:
            fig.add_trace(trace)

    fig.update_layout(
        plot_bgcolor=TRANSPARENT,
        paper_bgcolor=TRANSPARENT,
        margin=dict(l=20, r=20, t=20, b=40),
        xaxis_title="Time Period",
        yaxis_title="Energy Consumption (TWh)",
        legend=dict(orientation="v", yanchor="top", y=1, xanchor="left", x=1.02),
    )

    return fig


def demand_curve(df: pd.DataFrame, color_generator: "ColorManager") -> go.Figure:
    """
    Create a load duration curve plot.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame where each column represents a scenario and contains
        sorted demand values from highest to lowest
    color_generator : Callable[[str], str]
        Color generator function

    Returns
    -------
    go.Figure
        Plotly figure with demand duration curves
    """
    fig = go.Figure()
    for scenario in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df.index.values,
                y=df[scenario],
                mode="lines",
                marker=dict(color=color_generator.get_color(scenario)),
                name=scenario,
                showlegend=False,
            )
        )
    fig.update_layout(
        plot_bgcolor=TRANSPARENT,
        paper_bgcolor=TRANSPARENT,
        margin_b=0,
        margin_t=20,
        margin_l=20,
        margin_r=20,
        barmode="stack",
    )
    return fig


def area_plot(
    df: pd.DataFrame,
    color_generator: "ColorManager",
    scenario_name: str,
    metric: str = "demand",
) -> go.Figure:
    """
    Create a stacked area plot for a single scenario.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame with columns: year, end_use, and the metric column
    color_generator : Callable[[str], str]
        Color generator function
    scenario_name : str
        Name of the scenario for the plot title
    metric : str, optional
        Column name for the values to plot, by default "demand"

    Returns
    -------
    go.Figure
        Plotly figure with stacked area chart
    """
    fig = go.Figure()
    for end_use in df["end_use"].unique():
        end_use_df = df[df["end_use"] == end_use]
        fig.add_trace(
            go.Scatter(
                x=end_use_df["year"],
                y=end_use_df[metric],
                mode="lines",
                line=dict(color=color_generator.get_color(end_use)),
                showlegend=False,
                stackgroup="one",
            )
        )
    fig.update_layout(title=scenario_name)

    fig.update_layout(
        plot_bgcolor=TRANSPARENT,
        paper_bgcolor=TRANSPARENT,
        margin_b=50,
        margin_t=50,
        margin_l=10,
        margin_r=10,
    )

    return fig
