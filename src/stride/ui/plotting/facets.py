from typing import TYPE_CHECKING, Any

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from .utils import (
    TRANSPARENT,
    calculate_subplot_layout,
    create_faceted_traces,
    create_seasonal_annotations,
    determine_facet_layout,
    get_hoverlabel_style,
    get_plotly_template,
    update_faceted_layout,
)

if TYPE_CHECKING:
    from stride.ui.color_manager import ColorManager


def add_seasonal_line_traces(
    fig: go.Figure,
    df: pd.DataFrame,
    layout_config: dict[str, Any],
    color_generator: "ColorManager",
) -> None:
    """Add line traces for seasonal load plots."""
    years = sorted(df["year"].unique())
    line_styles = ["solid", "dash", "dot", "dashdot"]
    for i, facet_value in enumerate(layout_config["facet_categories"]):
        if layout_config["facet_col"]:
            row = (i // layout_config["cols"]) + 1
            col = (i % layout_config["cols"]) + 1
            facet_df = df[df[layout_config["facet_col"]] == facet_value]
        else:
            row, col = 1, 1
            facet_df = df
        for j, year in enumerate(years):
            year_df = facet_df[facet_df["year"] == year].sort_values("hour_of_day")
            if year_df.empty:
                continue
            show_legend = (i == 0) if layout_config["facet_col"] else True
            trace_kwargs = {
                "x": year_df["hour_of_day"],
                "y": year_df["value"],
                "mode": "lines",
                "name": str(year),
                "line": dict(
                    color=color_generator.get_color(str(year)),
                    dash=line_styles[j % len(line_styles)],
                    shape="spline",
                ),
                "showlegend": show_legend,
                "legendgroup": str(year),
            }
            if layout_config["facet_col"]:
                fig.add_trace(go.Scatter(**trace_kwargs), row=row, col=col)
            else:
                fig.add_trace(go.Scatter(**trace_kwargs))


def seasonal_load_lines(
    df: pd.DataFrame, color_generator: "ColorManager", template: str = "plotly_dark"
) -> go.Figure:
    """Create faceted subplots for seasonal load lines."""
    if df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="No data available", x=0.5, y=0.5, xref="paper", yref="paper", showarrow=False
        )
        return fig

    # Get hover label styling based on theme
    hoverlabel_style = get_hoverlabel_style(template)

    layout_config = determine_facet_layout(df)

    # Create figure
    if layout_config["facet_col"]:
        fig = make_subplots(
            rows=layout_config["rows"],
            cols=layout_config["cols"],
            subplot_titles=layout_config["subplot_titles"],
            row_titles=layout_config["row_titles"],
            shared_yaxes=True,
            vertical_spacing=0.12,
            horizontal_spacing=0.05,
        )
    else:
        fig = go.Figure()

    # Add traces
    add_seasonal_line_traces(fig, df, layout_config, color_generator)

    # Update layout
    if layout_config["facet_col"]:
        annotations_list = create_seasonal_annotations(layout_config)

        fig.update_layout(
            template=get_plotly_template(),
            plot_bgcolor=TRANSPARENT,
            paper_bgcolor=TRANSPARENT,
            margin=dict(l=60, r=20, t=80, b=80),
            showlegend=True,
            legend=dict(orientation="v", yanchor="top", y=1, xanchor="left", x=1.02),
            height=400 if layout_config["rows"] == 1 else 600,
            annotations=annotations_list,
            hoverlabel=hoverlabel_style,
            hovermode="x unified",
        )

        fig.update_xaxes(
            range=[0, 23],
            showgrid=True,
            gridwidth=1,
            gridcolor="lightgray",
            tickvals=[0, 6, 12, 18, 23],
            ticktext=["0", "6", "12", "18", "23"],
            showline=True,
            linewidth=1,
            linecolor="black",
            mirror=True,
            title_text="",
        )
        fig.update_yaxes(
            showline=True,
            linewidth=1,
            linecolor="black",
            mirror=True,
            title_text="",
        )

        # Add vertical lines at 6, 12, and 18 for all subplots
        for row_idx in range(1, layout_config["rows"] + 1):
            for col_idx in range(1, layout_config["cols"] + 1):
                for hour in [6, 12, 18]:
                    fig.add_vline(
                        x=hour,
                        line_dash="dot",
                        line_color="lightgray",
                        line_width=1,
                        row=row_idx,
                        col=col_idx,
                    )
    else:
        fig.update_layout(
            template=get_plotly_template(),
            plot_bgcolor=TRANSPARENT,
            paper_bgcolor=TRANSPARENT,
            margin=dict(l=20, r=20, t=20, b=40),
            xaxis_title="Hour of Day",
            yaxis_title="Average Power Demand (MW)",
            xaxis=dict(
                range=[0, 23],
                showgrid=True,
                gridwidth=1,
                gridcolor="lightgray",
                tickvals=[0, 6, 12, 18, 23],
                ticktext=["0", "6", "12", "18", "23"],
                showline=True,
                linewidth=1,
                linecolor="black",
                mirror=True,
            ),
            yaxis=dict(showline=True, linewidth=1, linecolor="black", mirror=True),
            legend=dict(orientation="v", yanchor="top", y=1, xanchor="left", x=1.02),
            hoverlabel=hoverlabel_style,
            hovermode="x unified",
        )

        # Add vertical lines for single plot
        for hour in [6, 12, 18]:
            fig.add_vline(x=hour, line_dash="dot", line_color="lightgray", line_width=1)

    return fig


def _determine_breakdown_config(df: pd.DataFrame) -> tuple[str | None, list[str]]:
    """Determine breakdown column and categories for area charts."""
    breakdown_col = None
    if "sector" in df.columns:
        breakdown_col = "sector"
    elif "end_use" in df.columns:
        breakdown_col = "end_use"
    elif "metric" in df.columns:
        breakdown_col = "metric"

    breakdown_categories = []
    if breakdown_col:
        breakdown_categories = sorted(df[breakdown_col].unique())

    return breakdown_col, breakdown_categories


def _add_stacked_area_traces(
    fig: go.Figure,
    df: pd.DataFrame,
    layout_config: dict[str, Any],
    color_generator: "ColorManager",
    breakdown_col: str | None,
    breakdown_categories: list[str],
) -> None:
    """Add stacked area traces to the figure for each facet."""
    for i, facet_value in enumerate(layout_config["facet_categories"]):
        if layout_config["facet_col"]:
            row = (i // layout_config["cols"]) + 1
            col = (i % layout_config["cols"]) + 1
            facet_df = df[df[layout_config["facet_col"]] == facet_value]
        else:
            row, col = 1, 1
            facet_df = df

        if breakdown_col and breakdown_categories:
            # Create stacked areas for each breakdown category
            for j, category in enumerate(breakdown_categories):
                category_df = facet_df[facet_df[breakdown_col] == category].sort_values(
                    "hour_of_day"
                )

                if category_df.empty:
                    continue

                show_legend = (i == 0) if layout_config["facet_col"] else True
                trace_kwargs = {
                    "x": category_df["hour_of_day"],
                    "y": category_df["value"],
                    "mode": "lines",
                    "name": category,
                    "line": dict(color=color_generator.get_color(category)),
                    "fill": "tonexty" if j > 0 else "tozeroy",
                    "stackgroup": f"facet_{i}" if layout_config["facet_col"] else "one",
                    "showlegend": show_legend,
                    "legendgroup": category,
                }

                if layout_config["facet_col"]:
                    fig.add_trace(go.Scatter(**trace_kwargs), row=row, col=col)
                else:
                    fig.add_trace(go.Scatter(**trace_kwargs))
        else:
            # Single area per facet when no breakdown column
            facet_df = facet_df.sort_values("hour_of_day")

            if facet_df.empty:
                continue

            trace_kwargs = {
                "x": facet_df["hour_of_day"],
                "y": facet_df["value"],
                "mode": "lines",
                "name": str(facet_value) if layout_config["facet_col"] else "Load",
                "line": dict(
                    color=color_generator.get_color(
                        str(facet_value) if layout_config["facet_col"] else "Load"
                    )
                ),
                "fill": "tozeroy",
                "showlegend": False,
            }

            if layout_config["facet_col"]:
                fig.add_trace(go.Scatter(**trace_kwargs), row=row, col=col)
            else:
                fig.add_trace(go.Scatter(**trace_kwargs))


def seasonal_load_area(
    df: pd.DataFrame, color_generator: "ColorManager", template: str = "plotly_dark"
) -> go.Figure:
    """Create faceted area charts for seasonal load patterns."""
    if df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="No data available", x=0.5, y=0.5, xref="paper", yref="paper", showarrow=False
        )
        return fig

    # Get hover label styling based on theme
    hoverlabel_style = get_hoverlabel_style(template)

    layout_config = determine_facet_layout(df)
    breakdown_col, breakdown_categories = _determine_breakdown_config(df)
    has_breakdown = breakdown_col is not None

    # Create figure
    if layout_config["facet_col"]:
        fig = make_subplots(
            rows=layout_config["rows"],
            cols=layout_config["cols"],
            subplot_titles=layout_config["subplot_titles"],
            row_titles=layout_config["row_titles"],
            shared_yaxes=True,
            vertical_spacing=0.12,
            horizontal_spacing=0.05,
        )
    else:
        fig = go.Figure()

    # Add area traces
    _add_stacked_area_traces(
        fig, df, layout_config, color_generator, breakdown_col, breakdown_categories
    )

    # Update layout
    if layout_config["facet_col"]:
        annotations_list = create_seasonal_annotations(layout_config)

        fig.update_layout(
            template=get_plotly_template(),
            plot_bgcolor=TRANSPARENT,
            paper_bgcolor=TRANSPARENT,
            margin=dict(l=60, r=20, t=80, b=80),
            showlegend=has_breakdown,
            legend=dict(orientation="v", yanchor="top", y=1, xanchor="left", x=1.02)
            if has_breakdown
            else None,
            height=400 if layout_config["rows"] == 1 else 600,
            annotations=annotations_list,
            hoverlabel=hoverlabel_style,
            hovermode="x unified",
        )

        fig.update_xaxes(
            range=[0, 23],
            showgrid=True,
            gridwidth=1,
            gridcolor="lightgray",
            tickvals=[0, 6, 12, 18, 23],
            ticktext=["0", "6", "12", "18", "23"],
            showline=True,
            linewidth=1,
            linecolor="black",
            mirror=True,
            title_text="",
        )
        fig.update_yaxes(showline=True, linewidth=1, linecolor="black", mirror=True, title_text="")
    else:
        fig.update_layout(
            template=get_plotly_template(),
            plot_bgcolor=TRANSPARENT,
            paper_bgcolor=TRANSPARENT,
            margin=dict(l=20, r=20, t=20, b=40),
            xaxis_title="Hour of Day",
            yaxis_title="Average Power Demand (MW)",
            xaxis=dict(
                range=[0, 23],
                showgrid=True,
                gridwidth=1,
                gridcolor="lightgray",
                tickvals=[0, 6, 12, 18, 23],
                ticktext=["0", "6", "12", "18", "23"],
                showline=True,
                linewidth=1,
                linecolor="black",
                mirror=True,
            ),
            yaxis=dict(showline=True, linewidth=1, linecolor="black", mirror=True),
            showlegend=has_breakdown,
            legend=dict(orientation="v", yanchor="top", y=1, xanchor="left", x=1.02)
            if has_breakdown
            else None,
            hoverlabel=hoverlabel_style,
            hovermode="x unified",
        )

    return fig


def faceted_time_series(
    df: pd.DataFrame,
    color_generator: "ColorManager",
    chart_type: str = "Line",
    group_by: str | None = None,
    value_col: str = "value",
    template: str = "plotly_dark",
) -> go.Figure:
    """
    Create faceted subplots for each scenario with shared legend.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame with columns: scenario, year, value, and optionally group_by column
    color_generator : Callable[[str], str]
        Color generator function
    chart_type : str
        "Line" or "Area" chart type
    group_by : str, optional
        Column name to group by (e.g., "sector", "end_use")
    value_col : str
        Column name for values

    Returns
    -------
    go.Figure
        Plotly figure with subplots for each scenario
    """
    # Get hover label styling based on theme
    hoverlabel_style = get_hoverlabel_style(template)

    scenarios = sorted(df["scenario"].unique())
    rows, cols = calculate_subplot_layout(len(scenarios))

    # Create subplots with scenario titles
    fig = make_subplots(
        rows=rows,
        cols=cols,
        subplot_titles=scenarios,
        shared_yaxes=True,
        vertical_spacing=0.08,
        horizontal_spacing=0.05,
    )

    # Create and add traces
    traces_info = create_faceted_traces(
        df, scenarios, color_generator, chart_type, group_by, value_col
    )
    for trace, row, col in traces_info:
        fig.add_trace(trace, row=row, col=col)

    # Update layout
    update_faceted_layout(fig, rows, group_by)

    # Add hover styling
    fig.update_layout(
        hoverlabel=hoverlabel_style,
        hovermode="x unified",
    )

    return fig
