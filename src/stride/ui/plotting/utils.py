from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go

if TYPE_CHECKING:
    from stride.ui.color_manager import ColorManager

TRANSPARENT = "rgba(0, 0, 0, 0)"
DEFAULT_BAR_COLOR = "rgba(0,0,200,0.8)"
# Theme-aware neutral gray colors
LIGHT_THEME_GRAY = "rgba(100, 100, 100, 0.8)"  # Darker gray for light backgrounds
DARK_THEME_GRAY = "rgba(180, 180, 180, 0.8)"  # Lighter gray for dark backgrounds


def get_neutral_color(template: str) -> str:
    """
    Get a neutral gray color appropriate for the given template.

    Parameters
    ----------
    template : str
        Plotly template name (e.g., 'plotly_white', 'plotly_dark')

    Returns
    -------
    str
        RGBA color string for neutral gray
    """
    if "dark" in template.lower():
        return DARK_THEME_GRAY
    else:
        return LIGHT_THEME_GRAY


def get_plotly_template() -> str:
    """
    Get the Plotly template for charts.

    Returns
    -------
    str
        Plotly template name (defaults to 'plotly_dark' to match app's default theme)
    """
    # Default to dark theme to match the app's default
    return "plotly_dark"


def determine_facet_layout(df: pd.DataFrame) -> dict[str, Any]:
    """
    Determine faceting layout based on available columns in DataFrame.
    Returns
    -------
    dict
        Layout configuration with keys: facet_col, facet_categories, rows, cols,
        subplot_titles, row_titles, has_season, has_day_type
    """
    has_season = "season" in df.columns
    has_day_type = "day_type" in df.columns
    if has_season and has_day_type:
        season_order = ["Winter", "Spring", "Summer", "Fall"]
        day_order = ["Weekday", "Weekend"]
        facet_categories = [
            f"{season} - {day_type}" for day_type in day_order for season in season_order
        ]
        facet_col = "season_day_type"
        df[facet_col] = df["season"].astype(str) + " - " + df["day_type"].astype(str)
        df[facet_col] = pd.Categorical(df[facet_col], categories=facet_categories, ordered=True)
        return {
            "facet_col": facet_col,
            "facet_categories": facet_categories,
            "rows": 2,
            "cols": 4,
            "subplot_titles": None,
            "row_titles": ["Weekday", "Weekend"],
            "has_season": has_season,
            "has_day_type": has_day_type,
        }
    elif has_season:
        season_order = ["Winter", "Spring", "Summer", "Fall"]
        df["season"] = pd.Categorical(df["season"], categories=season_order, ordered=True)
        return {
            "facet_col": "season",
            "facet_categories": season_order,
            "rows": 1,
            "cols": 4,
            "subplot_titles": None,
            "row_titles": None,
            "has_season": has_season,
            "has_day_type": has_day_type,
        }
    elif has_day_type:
        day_order = ["Weekday", "Weekend"]
        df["day_type"] = pd.Categorical(df["day_type"], categories=day_order, ordered=True)
        return {
            "facet_col": "day_type",
            "facet_categories": day_order,
            "rows": 1,
            "cols": 2,
            "subplot_titles": None,
            "row_titles": None,
            "has_season": has_season,
            "has_day_type": has_day_type,
        }
    else:
        return {
            "facet_col": None,
            "facet_categories": [None],
            "rows": 1,
            "cols": 1,
            "subplot_titles": None,
            "row_titles": None,
            "has_season": has_season,
            "has_day_type": has_day_type,
        }


def create_seasonal_annotations(layout_config: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Create annotations for seasonal plots based on layout configuration.
    Returns
    -------
    list
        List of annotation dictionaries for the plot
    """
    annotations_list = [
        # Shared x-axis title
        dict(
            text="Hour of Day",
            xref="paper",
            yref="paper",
            x=0.5,
            y=-0.08,
            xanchor="center",
            yanchor="top",
            font=dict(size=14),
            showarrow=False,
        ),
        # Shared y-axis title
        dict(
            text="Load (MW)",
            xref="paper",
            yref="paper",
            x=-0.08,
            y=0.5,
            xanchor="center",
            yanchor="middle",
            font=dict(size=14),
            textangle=-90,
            showarrow=False,
        ),
    ]
    # Add column titles based on grouping
    if layout_config["has_season"] and layout_config["has_day_type"]:
        season_order = ["Winter", "Spring", "Summer", "Fall"]
        for i, season in enumerate(season_order):
            x_pos = (i + 0.5) / layout_config["cols"]
            annotations_list.append(
                dict(
                    text=f"<b>{season}</b>",
                    xref="paper",
                    yref="paper",
                    x=x_pos,
                    y=1.05,
                    xanchor="center",
                    yanchor="bottom",
                    font=dict(size=16),
                    showarrow=False,
                )
            )
    elif layout_config["has_season"]:
        season_order = ["Winter", "Spring", "Summer", "Fall"]
        for i, season in enumerate(season_order):
            x_pos = (i + 0.5) / layout_config["cols"]
            annotations_list.append(
                dict(
                    text=f"<b>{season}</b>",
                    xref="paper",
                    yref="paper",
                    x=x_pos,
                    y=1.05,
                    xanchor="center",
                    yanchor="bottom",
                    font=dict(size=16),
                    showarrow=False,
                )
            )
    elif layout_config["has_day_type"]:
        day_order = ["Weekday", "Weekend"]
        for i, day_type in enumerate(day_order):
            x_pos = (i + 0.5) / layout_config["cols"]
            annotations_list.append(
                dict(
                    text=f"<b>{day_type}</b>",
                    xref="paper",
                    yref="paper",
                    x=x_pos,
                    y=1.05,
                    xanchor="center",
                    yanchor="bottom",
                    font=dict(size=16),
                    showarrow=False,
                )
            )
    return annotations_list


def numbers_under_each_bar(
    fig: go.Figure,
    n_groups: int,
    n_bars: int,
    labels: list[str] | None = None,
    sep_width: float = 0.2,
) -> go.Figure:
    """
    Add annotations above the middle bar group in a grouped bar chart.

    Parameters
    ----------
    fig : go.Figure
        Plotly figure to add annotations to
    n_groups : int
        Number of bar groups (x-axis positions)
    n_bars : int
        Number of bars per group
    labels : list[str], optional
        Labels to display above each bar. If None, uses numbers (1, 2, 3...), by default None
    sep_width : float, optional
        Separation width between bar groups, by default 0.2

    Returns
    -------
    go.Figure
        Modified figure with annotations above the middle bar group
    """
    # Position labels above the middle bar group
    middle_group = (n_groups + 1) // 2

    if labels is not None:
        bar_labels = labels
    else:
        bar_labels = [str(i) for i in range(1, n_bars + 1)]

    x = (np.arange(n_bars) - ((n_bars - 1) / 2)) * ((1 - sep_width) / n_bars)
    x = x + middle_group - 1

    for label, xi in zip(bar_labels, x):
        fig.add_annotation(
            text=f"<b>{label}</b>",
            y=1,
            x=xi,
            showarrow=False,
            yref="paper",
            yanchor="bottom",
            textangle=-45,
            xanchor="left",
        )
    return fig


def get_time_series_breakdown_info(
    df: pd.DataFrame, group_by: str | None = None
) -> dict[str, Any]:
    """
    Determine breakdown column and data structure for time series plotting.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame with time series data
    group_by : str, optional
        Explicit breakdown column name

    Returns
    -------
    dict
        Dictionary with breakdown_col, has_breakdown, and years
    """
    num_cols = len(df.columns)
    years = sorted(df["year"].unique())

    if num_cols == 4:
        return {"breakdown_col": None, "has_breakdown": False, "years": years}
    elif num_cols == 5:
        breakdown_col = (
            group_by
            if group_by
            else [
                col
                for col in df.columns
                if col not in ["scenario", "year", "time_period", "value"]
            ][0]
        )
        return {"breakdown_col": breakdown_col, "has_breakdown": True, "years": years}
    else:
        return {"breakdown_col": None, "has_breakdown": False, "years": years, "invalid": True}


def create_time_series_line_traces(
    df: pd.DataFrame, color_generator: "ColorManager", breakdown_info: dict[str, Any]
) -> list[go.Scatter]:
    """
    Create line traces for time series data.

    Parameters
    ----------
    df : pd.DataFrame
        Time series data
    color_generator : Callable
        Color generator function
    breakdown_info : dict
        Breakdown information from get_time_series_breakdown_info

    Returns
    -------
    list
        List of plotly traces
    """
    traces = []
    line_styles = ["solid", "dash", "dot", "dashdot"]
    years = breakdown_info["years"]

    if not breakdown_info["has_breakdown"]:
        # No breakdown - plot separate lines for each year
        for i, year in enumerate(years):
            year_df = df[df["year"] == year].sort_values("time_period")
            traces.append(
                go.Scatter(
                    x=year_df["time_period"],
                    y=year_df["value"],
                    mode="lines",
                    name=str(year),
                    line=dict(
                        color=color_generator.get_color(str(year)),
                        dash=line_styles[i % len(line_styles)],
                    ),
                    showlegend=True,
                )
            )
    else:
        # With breakdown - plot lines for each year and category combination
        breakdown_col = breakdown_info["breakdown_col"]
        categories = sorted(df[breakdown_col].unique())

        for i, year in enumerate(years):
            year_df = df[df["year"] == year]
            line_style = line_styles[i % len(line_styles)]

            for category in categories:
                category_df = year_df[year_df[breakdown_col] == category].sort_values(
                    "time_period"
                )

                if category_df.empty:
                    continue

                legend_name = f"{year} - {category}"
                traces.append(
                    go.Scatter(
                        x=category_df["time_period"],
                        y=category_df["value"],
                        mode="lines",
                        name=legend_name,
                        line=dict(
                            color=color_generator.get_color(category),
                            dash=line_style,
                        ),
                        legendgroup=category,
                        showlegend=True,
                    )
                )

    return traces


def create_time_series_area_traces(
    df: pd.DataFrame, color_generator: "ColorManager", breakdown_info: dict[str, Any]
) -> list[go.Scatter]:
    """
    Create area traces for time series data.

    Parameters
    ----------
    df : pd.DataFrame
        Time series data
    color_generator : Callable
        Color generator function
    breakdown_info : dict
        Breakdown information from get_time_series_breakdown_info

    Returns
    -------
    list
        List of plotly traces
    """
    traces = []
    years = breakdown_info["years"]

    if not breakdown_info["has_breakdown"]:
        # No breakdown - plot separate areas for each year
        for year in years:
            year_df = df[df["year"] == year].sort_values("time_period")
            traces.append(
                go.Scatter(
                    x=year_df["time_period"],
                    y=year_df["value"],
                    mode="lines",
                    name=str(year),
                    line=dict(color=color_generator.get_color(str(year))),
                    fill="tozeroy",
                    showlegend=True,
                )
            )
    else:
        # With breakdown - stack by category within each year
        breakdown_col = breakdown_info["breakdown_col"]
        categories = sorted(df[breakdown_col].unique())

        for i, year in enumerate(years):
            year_df = df[df["year"] == year]

            for j, category in enumerate(categories):
                category_df = year_df[year_df[breakdown_col] == category].sort_values(
                    "time_period"
                )

                if category_df.empty:
                    continue

                legend_name = f"{year} - {category}" if len(years) > 1 else category
                traces.append(
                    go.Scatter(
                        x=category_df["time_period"],
                        y=category_df["value"],
                        mode="lines",
                        name=legend_name,
                        line=dict(color=color_generator.get_color(category)),
                        fill="tonexty" if j > 0 else "tozeroy",
                        stackgroup=f"year_{year}",
                        legendgroup=category,
                        showlegend=True,
                    )
                )

    return traces


def calculate_subplot_layout(n_items: int) -> tuple[int, int]:
    """
    Calculate optimal subplot layout for given number of items.

    Parameters
    ----------
    n_items : int
        Number of items to arrange in subplots

    Returns
    -------
    tuple
        (rows, cols) for subplot arrangement
    """
    if n_items <= 3:
        return 1, n_items
    elif n_items <= 6:
        return 2, 3
    else:
        return 3, 3


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


def create_faceted_traces(
    df: pd.DataFrame,
    scenarios: list[str],
    color_generator: "ColorManager",
    chart_type: str,
    group_by: str | None = None,
    value_col: str = "value",
) -> list[tuple[go.Scatter, int, int]]:
    """
    Create traces for faceted time series plots.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame with scenario data
    scenarios : list
        List of scenario names
    color_generator : Callable
        Color generator function
    chart_type : str
        "Line" or "Area" chart type
    group_by : str, optional
        Column name to group by
    value_col : str
        Column name for values

    Returns
    -------
    list
        List of (trace, row, col, show_legend) tuples
    """
    rows, cols = calculate_subplot_layout(len(scenarios))
    traces_info = []

    if group_by:
        categories = sorted(df[group_by].unique())

        for i, scenario in enumerate(scenarios):
            row = (i // cols) + 1
            col = (i % cols) + 1
            scenario_df = df[df["scenario"] == scenario]

            for j, category in enumerate(categories):
                category_df = scenario_df[scenario_df[group_by] == category]
                if category_df.empty:
                    continue

                show_legend = i == 0
                trace = _create_single_trace(
                    category_df,
                    category,
                    color_generator,
                    chart_type,
                    value_col,
                    j,
                    show_legend,
                    category,
                )
                traces_info.append((trace, row, col))
    else:
        for i, scenario in enumerate(scenarios):
            row = (i // cols) + 1
            col = (i % cols) + 1
            scenario_df = df[df["scenario"] == scenario].sort_values("year")

            if scenario_df.empty:
                continue

            trace = _create_single_trace(
                scenario_df, scenario, color_generator, chart_type, value_col, 0, False, scenario
            )
            traces_info.append((trace, row, col))

    return traces_info


def _create_single_trace(
    data_df: pd.DataFrame,
    name: str,
    color_generator: "ColorManager",
    chart_type: str,
    value_col: str,
    stack_index: int,
    show_legend: bool,
    legend_group: str,
) -> go.Scatter:
    """Create a single trace for faceted plots."""
    base_kwargs: dict[str, Any] = {
        "x": data_df["year"],
        "y": data_df[value_col],
        "name": name,
        "line": dict(color=color_generator.get_color(legend_group)),
        "showlegend": show_legend,
        "legendgroup": legend_group,
    }

    if chart_type == "Area":
        base_kwargs.update(
            {
                "mode": "lines",
                "fill": "tonexty" if stack_index > 0 else "tozeroy",
                "stackgroup": "one",
            }
        )
    else:  # Line chart
        base_kwargs.update(
            {
                "mode": "lines+markers",
            }
        )

    return go.Scatter(**base_kwargs)


def update_faceted_layout(fig: go.Figure, rows: int, group_by: str | None = None) -> None:
    """
    Update layout for faceted time series plots.

    Parameters
    ----------
    fig : go.Figure
        Plotly figure to update
    rows : int
        Number of subplot rows
    group_by : str, optional
        Group by column name
    """
    height = 400 if rows == 1 else 600 if rows == 2 else 800

    fig.update_layout(
        plot_bgcolor=TRANSPARENT,
        paper_bgcolor=TRANSPARENT,
        margin=dict(l=20, r=20, t=60, b=40),
        showlegend=group_by is not None,
        legend=dict(orientation="v", yanchor="top", y=1, xanchor="left", x=1.02)
        if group_by
        else None,
        height=height,
    )

    fig.update_xaxes(title_text="Year")
    fig.update_yaxes(title_text="Energy Consumption (TWh)", col=1)
