from typing import TYPE_CHECKING, Any, Callable, Literal

import pandas as pd
import plotly.graph_objects as go
from dash import ALL, Input, Output, State, callback, ctx
from loguru import logger

from stride.api.utils import ChartType, ConsumptionBreakdown, SecondaryMetric
from stride.ui.plotting import StridePlots
from stride.ui.plotting.utils import (
    get_background_color,
    get_error_annotation_style,
    get_hoverlabel_style,
    get_warning_annotation_style,
)
from stride.ui.settings.layout import get_temp_color_edits

if TYPE_CHECKING:
    from stride.api import APIClient
    from stride.ui.color_manager import ColorManager
    from stride.ui.plotting import StridePlots


def get_secondary_metric_label(metric: str) -> str:
    """
    Get the display label with units for a secondary metric.

    Parameters
    ----------
    metric : str
        The metric name

    Returns
    -------
    str
        Display label with units
    """
    metric_labels = {
        "GDP": "GDP (Billion USD-2024)",
        "GDP Per Capita": "GDP Per Capita (USD-2024/person)",
    }
    return metric_labels.get(metric, metric)


def save_home_state(*values: object) -> dict[str, Any]:
    """
    Save the current state of all home tab inputs.

    Parameters
    ----------
    *values : tuple
        Values from all home input components

    Returns
    -------
    dict
        Dictionary mapping input IDs to their current values
    """
    home_input_ids = [
        "home-consumption-breakdown",
        "home-secondary-metric",
        "home-scenarios-checklist",
        "home-peak-breakdown",
        "home-peak-secondary-metric",
        "home-scenarios-2-checklist",
        "home-year-dropdown",
        "home-scenarios-3-checklist",
        "home-timeseries-chart-type",
        "home-timeseries-breakdown",
        "home-timeseries-secondary-metric",
        "home-scenarios-4-checklist",
    ]
    return dict(zip(home_input_ids, values))


def update_home_scenario_comparison(  # noqa: C901
    data_handler: "APIClient",
    plotter: "StridePlots",
    selected_scenarios: list[str],
    breakdown: ConsumptionBreakdown | Literal["None"],
    secondary_metric: SecondaryMetric | Literal["None"],
) -> go.Figure | dict[str, Any]:
    """
    Update the home scenario comparison chart showing annual electricity consumption.

    Parameters
    ----------
    data_handler : APIClient
        API client for data access
    plotter : StridePlots
        Plotting utilities for creating charts
    selected_scenarios : list[str]
        List of selected scenario names
    breakdown : str
        Breakdown type ("None", "Sector", or "End Use")
    secondary_metric : str
        Secondary metric for right axis

    Returns
    -------
    go.Figure or dict
        Plotly figure object or error dictionary
    """
    print(f"Callback triggered with scenarios: {selected_scenarios}, breakdown: {breakdown}")

    if not selected_scenarios:
        return {"data": [], "layout": {"title": "Select scenarios to view data"}}

    try:
        # Convert "None" to None
        breakdown_value = None if breakdown == "None" else breakdown

        # Get the main consumption data
        df = data_handler.get_annual_electricity_consumption(
            scenarios=selected_scenarios, group_by=breakdown_value
        )

        print(f"Retrieved data with shape: {df.shape}")

        # Create the main plot
        if breakdown_value:
            stack_col = "metric" if breakdown_value == "End Use" else str(breakdown_value)
            fig = plotter.grouped_stacked_bars(df, stack_col=stack_col.lower(), value_col="value")
        else:
            fig = plotter.grouped_single_bars(df, "scenario")

        # Add secondary metric if selected
        if secondary_metric and secondary_metric != "None":
            try:
                # Get secondary metric data for each selected scenario
                for scenario in selected_scenarios:
                    secondary_df = data_handler.get_secondary_metric(
                        scenario=scenario, metric=secondary_metric, years=None
                    )

                    if not secondary_df.empty:
                        # Get scenario color from color manager
                        scenario_color = plotter.color_manager.get_color(scenario)

                        # Add background line when no breakdown (total only)
                        if breakdown_value is None:
                            # Get theme-aware background color (matches plot background)
                            bg_color = get_background_color(plotter.get_template())

                            # Add background line (solid, thicker)
                            fig.add_trace(
                                go.Scatter(
                                    x=secondary_df["year"],
                                    y=secondary_df["value"],
                                    mode="lines",
                                    yaxis="y2",
                                    line=dict(width=5, color=bg_color),
                                    showlegend=False,
                                    hoverinfo="skip",
                                )
                            )

                        # Add secondary metric as a line trace on the right y-axis
                        fig.add_trace(
                            go.Scatter(
                                x=secondary_df["year"],
                                y=secondary_df["value"],
                                name=f"{scenario} - {secondary_metric}",
                                mode="lines+markers",
                                yaxis="y2",
                                line=dict(width=2, dash="dash", color=scenario_color),
                                marker=dict(size=6, color=scenario_color),
                                customdata=secondary_df["value"],
                                hovertemplate=f"{scenario} - {secondary_metric}: %{{customdata:.2f}}<extra></extra>",
                            )
                        )

                # Update layout to add secondary y-axis and unified hover styling
                hoverlabel_style = get_hoverlabel_style(plotter.get_template())
                fig.update_layout(
                    yaxis2=dict(
                        title=get_secondary_metric_label(secondary_metric),
                        overlaying="y",
                        side="right",
                    ),
                    legend=dict(orientation="v", yanchor="top", y=1.0, xanchor="left", x=1.05),
                    hoverlabel=hoverlabel_style,
                )
            except NotImplementedError as e:
                # Show error annotation on the plot for unsupported metrics
                error_style = get_error_annotation_style(plotter.get_template())
                fig.add_annotation(
                    text=f"⚠️ {str(e)}",
                    xref="paper",
                    yref="paper",
                    x=0.5,
                    y=1.05,
                    showarrow=False,
                    font=dict(size=12, color=error_style["font_color"]),
                    bgcolor=error_style["bgcolor"],
                    bordercolor=error_style["bordercolor"],
                    borderwidth=2,
                )
            except Exception as e:
                # Show error annotation for other errors (table not found, etc.)
                error_msg = str(e)
                if "does not exist" in error_msg.lower() or "not found" in error_msg.lower():
                    error_msg = f"Table not available for {secondary_metric}"

                error_style = get_error_annotation_style(plotter.get_template())
                fig.add_annotation(
                    text=f"⚠️ {error_msg}",
                    xref="paper",
                    yref="paper",
                    x=0.5,
                    y=1.05,
                    showarrow=False,
                    font=dict(size=12, color=error_style["font_color"]),
                    bgcolor=error_style["bgcolor"],
                    bordercolor=error_style["bordercolor"],
                    borderwidth=2,
                )
                logger.error(f"Secondary metric error: {e}")

        # Set primary y-axis label
        if secondary_metric and secondary_metric != "None":
            # When there's a secondary axis, only update the primary (left) axis
            fig.update_layout(yaxis=dict(title="Energy Consumption (MWh)"))
        else:
            # When there's no secondary axis, use the simpler update method
            fig.update_yaxes(title_text="Energy Consumption (MWh)")

        return fig

    except Exception as e:
        print(f"Error in update_home_scenario_comparison: {e}")
        import traceback

        traceback.print_exc()
        return {"data": [], "layout": {"title": f"Error: {str(e)}"}}


def update_home_sector_breakdown(  # noqa: C901
    data_handler: "APIClient",
    plotter: "StridePlots",
    selected_scenarios: list[str],
    breakdown: ConsumptionBreakdown | Literal["None"],
    secondary_metric: SecondaryMetric | Literal["None"],
) -> go.Figure | dict[str, Any]:
    """
    Update the home sector breakdown chart showing annual peak demand.

    Parameters
    ----------
    data_handler : APIClient
        API client for data access
    plotter : StridePlots
        Plotting utilities for creating charts
    selected_scenarios : list[str]
        List of selected scenario names
    breakdown : str
        Breakdown type ("None", "Sector", or "End Use")
    secondary_metric : str
        Secondary metric for right axis

    Returns
    -------
    go.Figure or dict
        Plotly figure object or error dictionary
    """
    print(
        f"Peak demand callback triggered with scenarios: {selected_scenarios}, breakdown: {breakdown}"
    )

    if not selected_scenarios:
        return {"data": [], "layout": {"title": "Select scenarios to view data"}}

    try:
        # Convert "None" to None
        breakdown_value = None if breakdown == "None" else breakdown

        # Get the peak demand data
        df = data_handler.get_annual_peak_demand(
            scenarios=selected_scenarios, group_by=breakdown_value
        )

        print(f"Retrieved peak demand data with shape: {df.shape}")

        # Create the main plot
        if breakdown_value:
            stack_col = "metric" if breakdown_value == "End Use" else str(breakdown_value)

            fig = plotter.grouped_stacked_bars(df, stack_col=stack_col.lower(), value_col="value")
        else:
            fig = plotter.grouped_single_bars(df, "scenario")

        # Add secondary metric if selected
        if secondary_metric and secondary_metric != "None":
            try:
                # Get secondary metric data for each selected scenario
                for scenario in selected_scenarios:
                    secondary_df = data_handler.get_secondary_metric(
                        scenario=scenario, metric=secondary_metric, years=None
                    )

                    if not secondary_df.empty:
                        # Get scenario color from color manager
                        scenario_color = plotter.color_manager.get_color(scenario)

                        # Add background line when no breakdown (total only)
                        if breakdown_value is None:
                            # Get theme-aware background color (matches plot background)
                            bg_color = get_background_color(plotter.get_template())

                            # Add background line (solid, thicker)
                            fig.add_trace(
                                go.Scatter(
                                    x=secondary_df["year"],
                                    y=secondary_df["value"],
                                    mode="lines",
                                    yaxis="y2",
                                    line=dict(width=5, color=bg_color),
                                    showlegend=False,
                                    hoverinfo="skip",
                                )
                            )

                        # Add secondary metric as a line trace on the right y-axis
                        fig.add_trace(
                            go.Scatter(
                                x=secondary_df["year"],
                                y=secondary_df["value"],
                                name=f"{scenario} - {secondary_metric}",
                                mode="lines+markers",
                                yaxis="y2",
                                line=dict(width=2, dash="dash", color=scenario_color),
                                marker=dict(size=6, color=scenario_color),
                                customdata=secondary_df["value"],
                                hovertemplate=f"{scenario} - {secondary_metric}: %{{customdata:.2f}}<extra></extra>",
                            )
                        )

                # Update layout to add secondary y-axis and unified hover styling
                hoverlabel_style = get_hoverlabel_style(plotter.get_template())
                fig.update_layout(
                    yaxis=dict(title="Power Demand (MW)"),
                    yaxis2=dict(
                        title=get_secondary_metric_label(secondary_metric),
                        overlaying="y",
                        side="right",
                    ),
                    legend=dict(orientation="v", yanchor="top", y=1.0, xanchor="left", x=1.05),
                    hoverlabel=hoverlabel_style,
                )
            except NotImplementedError as e:
                # Show error annotation on the plot for unsupported metrics
                error_style = get_error_annotation_style(plotter.get_template())
                fig.add_annotation(
                    text=f"⚠️ {str(e)}",
                    xref="paper",
                    yref="paper",
                    x=0.5,
                    y=1.05,
                    showarrow=False,
                    font=dict(size=12, color=error_style["font_color"]),
                    bgcolor=error_style["bgcolor"],
                    bordercolor=error_style["bordercolor"],
                    borderwidth=2,
                )
            except Exception as e:
                # Show error annotation for other errors (table not found, etc.)
                error_msg = str(e)
                if "does not exist" in error_msg.lower() or "not found" in error_msg.lower():
                    error_msg = f"Table not available for {secondary_metric}"

                error_style = get_error_annotation_style(plotter.get_template())
                fig.add_annotation(
                    text=f"⚠️ {error_msg}",
                    xref="paper",
                    yref="paper",
                    x=0.5,
                    y=1.05,
                    showarrow=False,
                    font=dict(size=12, color=error_style["font_color"]),
                    bgcolor=error_style["bgcolor"],
                    bordercolor=error_style["bordercolor"],
                    borderwidth=2,
                )
                logger.error(f"Secondary metric error: {e}")
        else:
            # No secondary metric - just update primary y-axis label
            fig.update_layout(yaxis=dict(title="Power Demand (MW)"))

        return fig

    except Exception as e:
        print(f"Error in update_home_sector_breakdown: {e}")
        import traceback

        traceback.print_exc()
        return {"data": [], "layout": {"title": f"Error: {str(e)}"}}


def update_home_load_duration(
    data_handler: "APIClient",
    plotter: "StridePlots",
    selected_scenarios: list[str],
    selected_year: int | str,
) -> go.Figure | dict[str, Any]:
    """
    Update the home load duration curve chart.

    Parameters
    ----------
    data_handler : APIClient
        API client for data access
    plotter : StridePlots
        Plotting utilities for creating charts
    selected_scenarios : list[str]
        List of selected scenario names
    selected_year : int | str
        Selected year for load duration curve (UI may pass string)

    Returns
    -------
    go.Figure or dict
        Plotly figure object or empty dictionary if no data
    """
    if not selected_scenarios or not selected_year:
        return {}

    try:
        # Convert year to int and wrap in list (UI may pass string)
        year_int = int(selected_year) if not isinstance(selected_year, int) else selected_year
        df = data_handler.get_load_duration_curve(years=[year_int], scenarios=selected_scenarios)
        return plotter.demand_curve(df)
    except Exception as e:
        logger.trace(e)
        return {}


def update_home_scenario_timeseries(  # noqa: C901
    data_handler: "APIClient",
    plotter: "StridePlots",
    selected_scenarios: list[str],
    chart_type: ChartType,
    breakdown: ConsumptionBreakdown | Literal["None"],
    secondary_metric: SecondaryMetric | Literal["None"],
) -> go.Figure | dict[str, Any]:
    """
    Update the home scenario timeseries chart.

    Parameters
    ----------
    data_handler : APIClient
        API client for data access
    plotter : StridePlots
        Plotting utilities for creating charts
    selected_scenarios : list[str]
        List of selected scenario names
    chart_type : str
        Type of chart to display
    breakdown : str
        Breakdown type ("None", "Sector", or "End Use")
    secondary_metric : str
        Secondary metric for right axis

    Returns
    -------
    go.Figure or dict
        Plotly figure object or error dictionary
    """
    print(
        f"Timeseries callback triggered with scenarios: {selected_scenarios}, chart_type: {chart_type}, breakdown: {breakdown}"
    )

    if not selected_scenarios:
        return {"data": [], "layout": {"title": "Select scenarios to view data"}}

    try:
        # Convert "None" to None
        breakdown_value = None if breakdown == "None" else breakdown

        # Get the consumption data for all scenarios
        df = data_handler.get_annual_electricity_consumption(
            scenarios=selected_scenarios, group_by=breakdown_value
        )

        print(f"Retrieved timeseries data with shape: {df.shape}")

        stack_col = "metric" if breakdown_value == "End Use" else str(breakdown_value)

        # Check if secondary metric is selected - if so, recreate chart with secondary axes
        if secondary_metric and secondary_metric != "None":
            try:
                # Collect all secondary metric data
                secondary_data = []
                for scenario in selected_scenarios:
                    try:
                        secondary_df = data_handler.get_secondary_metric(
                            scenario=scenario, metric=secondary_metric, years=None
                        )
                        if not secondary_df.empty:
                            secondary_df["scenario"] = scenario
                            secondary_data.append(secondary_df)
                    except Exception as inner_e:
                        logger.warning(
                            f"Could not fetch {secondary_metric} for {scenario}: {inner_e}"
                        )
                        continue

                if secondary_data:
                    # Combine all secondary data
                    all_secondary_df = pd.concat(secondary_data, ignore_index=True)

                    # Calculate subplot layout
                    num_scenarios = len(selected_scenarios)
                    if num_scenarios <= 3:
                        rows, cols = 1, num_scenarios
                    elif num_scenarios <= 6:
                        rows, cols = 2, 3
                    else:
                        rows, cols = 3, 3

                    # Create specs for make_subplots with secondary y-axes
                    from plotly.subplots import make_subplots

                    specs: list[list[dict[str, str | bool | int | float] | None]] = [
                        [{"secondary_y": True} for _ in range(cols)] for _ in range(rows)
                    ]

                    # Create figure with secondary y-axes (preserve scenario order)
                    fig = make_subplots(
                        rows=rows,
                        cols=cols,
                        subplot_titles=selected_scenarios,
                        specs=specs,
                        shared_yaxes=True,
                        vertical_spacing=0.08,
                        horizontal_spacing=0.05,
                    )

                    # Add primary data traces
                    if breakdown_value:
                        categories = sorted(df[stack_col.lower()].unique())
                        for idx, scenario in enumerate(selected_scenarios):
                            row = (idx // cols) + 1
                            col = (idx % cols) + 1
                            scenario_df = df[df["scenario"] == scenario]

                            for j, category in enumerate(categories):
                                category_df = scenario_df[
                                    scenario_df[stack_col.lower()] == category
                                ]
                                if not category_df.empty:
                                    show_legend = idx == 0
                                    if chart_type == "Area":
                                        fig.add_trace(
                                            go.Scatter(
                                                x=category_df["year"],
                                                y=category_df["value"],
                                                name=category,
                                                mode="lines",
                                                line=dict(
                                                    color=plotter.color_manager.get_color(category)
                                                ),
                                                fill="tonexty" if j > 0 else "tozeroy",
                                                stackgroup="one",
                                                showlegend=show_legend,
                                                legendgroup=category,
                                                hovertemplate="Year: %{x}<br>"
                                                + f"{category}: %{{y:.2f}}<br>"
                                                + "<extra></extra>",
                                            ),
                                            row=row,
                                            col=col,
                                            secondary_y=False,
                                        )
                                    else:  # Line
                                        fig.add_trace(
                                            go.Scatter(
                                                x=category_df["year"],
                                                y=category_df["value"],
                                                name=category,
                                                mode="lines+markers",
                                                line=dict(
                                                    color=plotter.color_manager.get_color(category)
                                                ),
                                                showlegend=show_legend,
                                                legendgroup=category,
                                                hovertemplate="Year: %{x}<br>"
                                                + f"{category}: %{{y:.2f}}<br>"
                                                + "<extra></extra>",
                                            ),
                                            row=row,
                                            col=col,
                                            secondary_y=False,
                                        )
                    else:
                        # No breakdown - simple line/area per scenario
                        for idx, scenario in enumerate(selected_scenarios):
                            row = (idx // cols) + 1
                            col = (idx % cols) + 1
                            scenario_df = df[df["scenario"] == scenario].sort_values("year")

                            if not scenario_df.empty:
                                if chart_type == "Area":
                                    fig.add_trace(
                                        go.Scatter(
                                            x=scenario_df["year"],
                                            y=scenario_df["value"],
                                            name=scenario,
                                            mode="lines",
                                            line=dict(
                                                color=plotter.color_manager.get_color(scenario)
                                            ),
                                            fill="tozeroy",
                                            showlegend=False,
                                            hovertemplate="Year: %{x}<br>"
                                            + f"{scenario}: %{{y:.2f}}<br>"
                                            + "<extra></extra>",
                                        ),
                                        row=row,
                                        col=col,
                                        secondary_y=False,
                                    )
                                else:  # Line
                                    fig.add_trace(
                                        go.Scatter(
                                            x=scenario_df["year"],
                                            y=scenario_df["value"],
                                            name=scenario,
                                            mode="lines+markers",
                                            line=dict(
                                                color=plotter.color_manager.get_color(scenario)
                                            ),
                                            showlegend=False,
                                            hovertemplate="Year: %{x}<br>"
                                            + f"{scenario}: %{{y:.2f}}<br>"
                                            + "<extra></extra>",
                                        ),
                                        row=row,
                                        col=col,
                                        secondary_y=False,
                                    )

                    # Add secondary metric traces
                    for idx, scenario in enumerate(selected_scenarios):
                        scenario_secondary = all_secondary_df[
                            all_secondary_df["scenario"] == scenario
                        ]
                        if not scenario_secondary.empty:
                            row = (idx // cols) + 1
                            col = (idx % cols) + 1
                            scenario_color = plotter.color_manager.get_color(scenario)

                            fig.add_trace(
                                go.Scatter(
                                    x=scenario_secondary["year"],
                                    y=scenario_secondary["value"],
                                    name=secondary_metric,
                                    mode="lines+markers",
                                    line=dict(width=2, dash="dash", color=scenario_color),
                                    marker=dict(size=6, color=scenario_color, symbol="diamond"),
                                    legendgroup=secondary_metric,
                                    showlegend=(idx == 0),
                                    hovertemplate="Year: %{x}<br>"
                                    + f"{secondary_metric}: %{{y:.2f}}<br>"
                                    + "<extra></extra>",
                                ),
                                row=row,
                                col=col,
                                secondary_y=True,
                            )

                    # Update axes labels - only on rightmost column for secondary
                    for idx in range(len(selected_scenarios)):
                        row = (idx // cols) + 1
                        col = (idx % cols) + 1
                        fig.update_yaxes(
                            title_text="Energy Consumption (MWh)",
                            row=row,
                            col=col,
                            secondary_y=False,
                        )
                        if col == cols:  # Only rightmost column
                            fig.update_yaxes(
                                title_text=get_secondary_metric_label(secondary_metric),
                                row=row,
                                col=col,
                                secondary_y=True,
                            )

                    # Update layout with unified hover styling
                    hoverlabel_style = get_hoverlabel_style(plotter.get_template())
                    fig.update_layout(
                        template=plotter.get_template(),
                        height=400 if rows == 1 else 600,
                        hovermode="x",
                        legend=dict(orientation="v", yanchor="top", y=1, xanchor="left", x=1.02),
                        margin=dict(l=60, r=80, t=80, b=80),
                        hoverlabel=hoverlabel_style,
                    )
                else:
                    # No secondary data available - create normal chart with warning
                    fig = plotter.faceted_time_series(
                        df,
                        chart_type=chart_type,
                        group_by=stack_col.lower() if breakdown_value else None,
                        value_col="value",
                    )
                    warning_style = get_warning_annotation_style(plotter.get_template())
                    fig.add_annotation(
                        text=f"⚠️ No data available for {secondary_metric}",
                        xref="paper",
                        yref="paper",
                        x=0.5,
                        y=1.02,
                        showarrow=False,
                        font=dict(size=12, color=warning_style["font_color"]),
                        bgcolor=warning_style["bgcolor"],
                        bordercolor=warning_style["bordercolor"],
                        borderwidth=2,
                    )
            except NotImplementedError as e:
                # Create normal chart with error message
                fig = plotter.faceted_time_series(
                    df,
                    chart_type=chart_type,
                    group_by=stack_col.lower() if breakdown_value else None,
                    value_col="value",
                )
                error_style = get_error_annotation_style(plotter.get_template())
                fig.add_annotation(
                    text=f"⚠️ {str(e)}",
                    xref="paper",
                    yref="paper",
                    x=0.5,
                    y=1.02,
                    showarrow=False,
                    font=dict(size=12, color=error_style["font_color"]),
                    bgcolor=error_style["bgcolor"],
                    bordercolor=error_style["bordercolor"],
                    borderwidth=2,
                )
            except Exception as e:
                # Create normal chart with error message
                fig = plotter.faceted_time_series(
                    df,
                    chart_type=chart_type,
                    group_by=stack_col.lower() if breakdown_value else None,
                    value_col="value",
                )
                error_msg = str(e)
                if "does not exist" in error_msg.lower() or "not found" in error_msg.lower():
                    error_msg = f"Table not available for {secondary_metric}"

                error_style = get_error_annotation_style(plotter.get_template())
                fig.add_annotation(
                    text=f"⚠️ {error_msg}",
                    xref="paper",
                    yref="paper",
                    x=0.5,
                    y=1.02,
                    showarrow=False,
                    font=dict(size=12, color=error_style["font_color"]),
                    bgcolor=error_style["bgcolor"],
                    bordercolor=error_style["bordercolor"],
                    borderwidth=2,
                )
                logger.error(f"Secondary metric error: {e}")
        else:
            # No secondary metric - create normal faceted chart
            fig = plotter.faceted_time_series(
                df,
                chart_type=chart_type,
                group_by=stack_col.lower() if breakdown_value else None,
                value_col="value",
            )

        return fig

    except Exception as e:
        print(f"Error in update_home_scenario_timeseries: {e}")
        import traceback

        traceback.print_exc()
        return {"data": [], "layout": {"title": f"Error: {str(e)}"}}


def register_home_callbacks(  # noqa: C901
    get_data_handler_func: Callable[[], "APIClient | None"],
    get_plotter_func: Callable[[], "StridePlots | None"],
    scenarios: list[str],
    sectors: list[str],
    years: list[int],
    get_color_manager_func: Callable[[], "ColorManager | None"],
) -> None:
    """
    Register all callbacks for the home module.

    Parameters
    ----------
    get_data_handler_func : callable
        Function to get the current data handler instance
    get_plotter_func : callable
        Function to get the current plotter instance
    scenarios : list[str]
        List of available scenarios
    sectors : list[str]
        List of available sectors
    years : list[int]
        List of available years
    get_color_manager_func : callable
        Function to get the current color manager instance
    """

    # Scenario button callbacks for each checklist
    # Callback 1: home-scenarios-checklist
    @callback(
        Output("home-scenarios-checklist", "data"),
        Input({"type": "home-scenarios-checklist", "index": ALL}, "n_clicks"),
        State("home-scenarios-checklist", "data"),
        prevent_initial_call=True,
    )
    def _update_scenario_selection_1(
        n_clicks: list[int], current_selection: list[str]
    ) -> list[str]:
        """Toggle scenario selection when button is clicked."""
        if not ctx.triggered:
            return current_selection

        triggered_id = ctx.triggered_id
        if not triggered_id or not isinstance(triggered_id, dict):
            return current_selection

        clicked_scenario = triggered_id["index"]
        new_selection = current_selection.copy() if current_selection else []

        if clicked_scenario in new_selection:
            if len(new_selection) <= 1:
                return new_selection
            new_selection.remove(clicked_scenario)
        else:
            new_selection.append(clicked_scenario)

        return new_selection

    @callback(
        Output({"type": "home-scenarios-checklist", "index": ALL}, "style"),
        Input("home-scenarios-checklist", "data"),
        Input("settings-palette-applied", "data"),
        Input("color-edits-counter", "data"),
        State({"type": "home-scenarios-checklist", "index": ALL}, "id"),
        prevent_initial_call=False,
    )
    def _update_button_styles_1(
        selected_scenarios: list[str],
        palette_data: dict[str, Any],
        color_edits: int,
        button_ids: list[dict[str, str]],
    ) -> list[dict[str, Any]]:
        """Update button styles based on selected scenarios."""
        # Get the current color manager to ensure we have the latest palette
        current_color_manager = get_color_manager_func()
        if current_color_manager is None:
            return [{}] * len(button_ids)

        # Get temporary color edits
        temp_edits = get_temp_color_edits()

        styles = []
        selected_scenarios = selected_scenarios or []

        for button_id in button_ids:
            scenario = button_id["index"]
            is_selected = scenario in selected_scenarios

            # Check if there's a temporary edit for this scenario
            if scenario in temp_edits:
                base_color = temp_edits[scenario]
                # Temp edits are stored as hex, convert to rgba
                if base_color.startswith("#"):
                    base_color = current_color_manager._hex_to_rgba_str(base_color)
            else:
                base_color = current_color_manager.get_color(scenario)
            r, g, b, _ = current_color_manager._str_to_rgba(base_color)

            alpha = 0.9 if is_selected else 0.3
            bg_color = f"rgba({r}, {g}, {b}, {alpha})"
            border_color = f"rgba({r}, {g}, {b}, 1.0)"

            style = {
                "backgroundColor": bg_color,
                "borderColor": border_color,
                "borderWidth": "2px",
                "borderStyle": "solid",
                "borderRadius": "8px",
                "padding": "8px 16px",
                "margin": "4px",
                "cursor": "pointer",
                "fontWeight": "bold" if is_selected else "normal",
                "fontSize": "0.95rem",
                "transition": "all 0.2s ease",
                "color": "#212529",
            }
            styles.append(style)

        return styles

    # Callback 2: home-scenarios-2-checklist
    @callback(
        Output("home-scenarios-2-checklist", "data"),
        Input({"type": "home-scenarios-2-checklist", "index": ALL}, "n_clicks"),
        State("home-scenarios-2-checklist", "data"),
        prevent_initial_call=True,
    )
    def _update_scenario_selection_2(
        n_clicks: list[int], current_selection: list[str]
    ) -> list[str]:
        """Toggle scenario selection when button is clicked."""
        if not ctx.triggered:
            return current_selection

        triggered_id = ctx.triggered_id
        if not triggered_id or not isinstance(triggered_id, dict):
            return current_selection

        clicked_scenario = triggered_id["index"]
        new_selection = current_selection.copy() if current_selection else []

        if clicked_scenario in new_selection:
            if len(new_selection) <= 1:
                return new_selection
            new_selection.remove(clicked_scenario)
        else:
            new_selection.append(clicked_scenario)

        return new_selection

    @callback(
        Output({"type": "home-scenarios-2-checklist", "index": ALL}, "style"),
        Input("home-scenarios-2-checklist", "data"),
        Input("settings-palette-applied", "data"),
        Input("color-edits-counter", "data"),
        State({"type": "home-scenarios-2-checklist", "index": ALL}, "id"),
        prevent_initial_call=False,
    )
    def _update_button_styles_2(
        selected_scenarios: list[str],
        palette_data: dict[str, Any],
        color_edits: int,
        button_ids: list[dict[str, str]],
    ) -> list[dict[str, Any]]:
        """Update button styles based on selected scenarios."""
        # Get the current color manager to ensure we have the latest palette
        current_color_manager = get_color_manager_func()
        if current_color_manager is None:
            return [{}] * len(button_ids)

        # Get temporary color edits
        temp_edits = get_temp_color_edits()

        styles = []
        selected_scenarios = selected_scenarios or []

        for button_id in button_ids:
            scenario = button_id["index"]
            is_selected = scenario in selected_scenarios

            # Check if there's a temporary edit for this scenario
            if scenario in temp_edits:
                base_color = temp_edits[scenario]
                # Temp edits are stored as hex, convert to rgba
                if base_color.startswith("#"):
                    base_color = current_color_manager._hex_to_rgba_str(base_color)
            else:
                base_color = current_color_manager.get_color(scenario)
            r, g, b, _ = current_color_manager._str_to_rgba(base_color)

            alpha = 0.9 if is_selected else 0.3
            bg_color = f"rgba({r}, {g}, {b}, {alpha})"
            border_color = f"rgba({r}, {g}, {b}, 1.0)"

            style = {
                "backgroundColor": bg_color,
                "borderColor": border_color,
                "borderWidth": "2px",
                "borderStyle": "solid",
                "borderRadius": "8px",
                "padding": "8px 16px",
                "margin": "4px",
                "cursor": "pointer",
                "fontWeight": "bold" if is_selected else "normal",
                "fontSize": "0.95rem",
                "transition": "all 0.2s ease",
                "color": "#212529",
            }
            styles.append(style)

        return styles

    # Callback 3: home-scenarios-3-checklist
    @callback(
        Output("home-scenarios-3-checklist", "data"),
        Input({"type": "home-scenarios-3-checklist", "index": ALL}, "n_clicks"),
        State("home-scenarios-3-checklist", "data"),
        prevent_initial_call=True,
    )
    def _update_scenario_selection_3(
        n_clicks: list[int], current_selection: list[str]
    ) -> list[str]:
        """Toggle scenario selection when button is clicked."""
        if not ctx.triggered:
            return current_selection

        triggered_id = ctx.triggered_id
        if not triggered_id or not isinstance(triggered_id, dict):
            return current_selection

        clicked_scenario = triggered_id["index"]
        new_selection = current_selection.copy() if current_selection else []

        if clicked_scenario in new_selection:
            if len(new_selection) <= 1:
                return new_selection
            new_selection.remove(clicked_scenario)
        else:
            new_selection.append(clicked_scenario)

        return new_selection

    @callback(
        Output({"type": "home-scenarios-3-checklist", "index": ALL}, "style"),
        Input("home-scenarios-3-checklist", "data"),
        Input("settings-palette-applied", "data"),
        Input("color-edits-counter", "data"),
        State({"type": "home-scenarios-3-checklist", "index": ALL}, "id"),
        prevent_initial_call=False,
    )
    def _update_button_styles_3(
        selected_scenarios: list[str],
        palette_data: dict[str, Any],
        color_edits: int,
        button_ids: list[dict[str, str]],
    ) -> list[dict[str, Any]]:
        """Update button styles based on selected scenarios."""
        # Get the current color manager to ensure we have the latest palette
        current_color_manager = get_color_manager_func()
        if current_color_manager is None:
            return [{}] * len(button_ids)

        # Get temporary color edits
        temp_edits = get_temp_color_edits()

        styles = []
        selected_scenarios = selected_scenarios or []

        for button_id in button_ids:
            scenario = button_id["index"]
            is_selected = scenario in selected_scenarios

            # Check if there's a temporary edit for this scenario
            if scenario in temp_edits:
                base_color = temp_edits[scenario]
                # Temp edits are stored as hex, convert to rgba
                if base_color.startswith("#"):
                    base_color = current_color_manager._hex_to_rgba_str(base_color)
            else:
                base_color = current_color_manager.get_color(scenario)
            r, g, b, _ = current_color_manager._str_to_rgba(base_color)

            alpha = 0.9 if is_selected else 0.3
            bg_color = f"rgba({r}, {g}, {b}, {alpha})"
            border_color = f"rgba({r}, {g}, {b}, 1.0)"

            style = {
                "backgroundColor": bg_color,
                "borderColor": border_color,
                "borderWidth": "2px",
                "borderStyle": "solid",
                "borderRadius": "8px",
                "padding": "8px 16px",
                "margin": "4px",
                "cursor": "pointer",
                "fontWeight": "bold" if is_selected else "normal",
                "fontSize": "0.95rem",
                "transition": "all 0.2s ease",
                "color": "#212529",
            }
            styles.append(style)

        return styles

    # Callback 4: home-scenarios-4-checklist
    @callback(
        Output("home-scenarios-4-checklist", "data"),
        Input({"type": "home-scenarios-4-checklist", "index": ALL}, "n_clicks"),
        State("home-scenarios-4-checklist", "data"),
        prevent_initial_call=True,
    )
    def _update_scenario_selection_4(
        n_clicks: list[int], current_selection: list[str]
    ) -> list[str]:
        """Toggle scenario selection when button is clicked."""
        if not ctx.triggered:
            return current_selection

        triggered_id = ctx.triggered_id
        if not triggered_id or not isinstance(triggered_id, dict):
            return current_selection

        clicked_scenario = triggered_id["index"]
        new_selection = current_selection.copy() if current_selection else []

        if clicked_scenario in new_selection:
            if len(new_selection) <= 1:
                return new_selection
            new_selection.remove(clicked_scenario)
        else:
            new_selection.append(clicked_scenario)

        return new_selection

    @callback(
        Output({"type": "home-scenarios-4-checklist", "index": ALL}, "style"),
        Input("home-scenarios-4-checklist", "data"),
        Input("settings-palette-applied", "data"),
        Input("color-edits-counter", "data"),
        State({"type": "home-scenarios-4-checklist", "index": ALL}, "id"),
        prevent_initial_call=False,
    )
    def _update_button_styles_4(
        selected_scenarios: list[str],
        palette_data: dict[str, Any],
        color_edits: int,
        button_ids: list[dict[str, str]],
    ) -> list[dict[str, Any]]:
        """Update button styles based on selected scenarios."""
        # Get the current color manager to ensure we have the latest palette
        current_color_manager = get_color_manager_func()
        if current_color_manager is None:
            return [{}] * len(button_ids)

        # Get temporary color edits
        temp_edits = get_temp_color_edits()

        styles = []
        selected_scenarios = selected_scenarios or []

        for button_id in button_ids:
            scenario = button_id["index"]
            is_selected = scenario in selected_scenarios

            # Check if there's a temporary edit for this scenario
            if scenario in temp_edits:
                base_color = temp_edits[scenario]
                # Temp edits are stored as hex, convert to rgba
                if base_color.startswith("#"):
                    base_color = current_color_manager._hex_to_rgba_str(base_color)
            else:
                base_color = current_color_manager.get_color(scenario)
            r, g, b, _ = current_color_manager._str_to_rgba(base_color)

            alpha = 0.9 if is_selected else 0.3
            bg_color = f"rgba({r}, {g}, {b}, {alpha})"
            border_color = f"rgba({r}, {g}, {b}, 1.0)"

            style = {
                "backgroundColor": bg_color,
                "borderColor": border_color,
                "borderWidth": "2px",
                "borderStyle": "solid",
                "borderRadius": "8px",
                "padding": "8px 16px",
                "margin": "4px",
                "cursor": "pointer",
                "fontWeight": "bold" if is_selected else "normal",
                "fontSize": "0.95rem",
                "transition": "all 0.2s ease",
                "color": "#212529",
            }
            styles.append(style)

        return styles

    # State management callbacks
    home_input_ids = [
        "home-consumption-breakdown",
        "home-secondary-metric",
        "home-scenarios-checklist",
        "home-peak-breakdown",
        "home-peak-secondary-metric",
        "home-scenarios-2-checklist",
        "home-year-dropdown",
        "home-scenarios-3-checklist",
        "home-timeseries-chart-type",
        "home-timeseries-breakdown",
        "home-timeseries-secondary-metric",
        "home-scenarios-4-checklist",
    ]

    # Save home tab state
    @callback(
        Output("home-state-store", "data"),
        [Input(input_id, "data") for input_id in home_input_ids],
        prevent_initial_call=True,
    )
    def _save_home_state_callback(*values: Any) -> dict[str, Any]:
        return save_home_state(*values)

    # Home tab callbacks - now using "data" instead of "value" for stores
    @callback(
        Output("home-scenario-comparison", "figure"),
        Input("home-scenarios-checklist", "data"),
        Input("home-consumption-breakdown", "value"),
        Input("home-secondary-metric", "value"),
        Input("chart-refresh-trigger", "data"),
    )
    def _update_home_scenario_comparison_chart(
        selected_scenarios: list[str],
        breakdown: ConsumptionBreakdown | Literal["None"],
        secondary_metric: SecondaryMetric | Literal["None"],
        refresh_trigger: int,
    ) -> go.Figure:
        """Update the home scenario comparison chart."""
        data_handler = get_data_handler_func()
        plotter = get_plotter_func()
        if data_handler is None or plotter is None:
            return go.Figure()
        result = update_home_scenario_comparison(
            data_handler, plotter, selected_scenarios, breakdown, secondary_metric
        )
        return result if isinstance(result, go.Figure) else go.Figure(result)

    @callback(
        Output("home-sector-breakdown", "figure"),
        Input("home-scenarios-2-checklist", "data"),
        Input("home-peak-breakdown", "value"),
        Input("home-peak-secondary-metric", "value"),
        Input("chart-refresh-trigger", "data"),
    )
    def _update_home_sector_breakdown_chart(
        selected_scenarios: list[str],
        breakdown: ConsumptionBreakdown | Literal["None"],
        secondary_metric: SecondaryMetric | Literal["None"],
        refresh_trigger: int,
    ) -> go.Figure:
        """Update the home sector breakdown chart."""
        data_handler = get_data_handler_func()
        plotter = get_plotter_func()
        if data_handler is None or plotter is None:
            return go.Figure()
        result = update_home_sector_breakdown(
            data_handler, plotter, selected_scenarios, breakdown, secondary_metric
        )
        return result if isinstance(result, go.Figure) else go.Figure(result)

    @callback(
        Output("home-load-duration", "figure"),
        Input("home-scenarios-3-checklist", "data"),
        Input("home-year-dropdown", "value"),
        Input("chart-refresh-trigger", "data"),
    )
    def _update_home_load_duration_chart(
        selected_scenarios: list[str], year: int, refresh_trigger: int
    ) -> go.Figure:
        """Update the home load duration chart."""
        data_handler = get_data_handler_func()
        plotter = get_plotter_func()
        if data_handler is None or plotter is None:
            return go.Figure()
        result = update_home_load_duration(data_handler, plotter, selected_scenarios, year)
        return result if isinstance(result, go.Figure) else go.Figure(result)

    @callback(
        Output("home-scenario-timeseries", "figure"),
        Input("home-scenarios-4-checklist", "data"),
        Input("home-timeseries-chart-type", "value"),
        Input("home-timeseries-breakdown", "value"),
        Input("home-timeseries-secondary-metric", "value"),
        Input("chart-refresh-trigger", "data"),
    )
    def _update_home_scenario_timeseries_chart(
        selected_scenarios: list[str],
        chart_type: ChartType,
        breakdown: ConsumptionBreakdown | Literal["None"],
        secondary_metric: SecondaryMetric | Literal["None"],
        refresh_trigger: int,
    ) -> go.Figure:
        """Update the home scenario timeseries chart."""
        data_handler = get_data_handler_func()
        plotter = get_plotter_func()
        if data_handler is None or plotter is None:
            return go.Figure()
        result = update_home_scenario_timeseries(
            data_handler, plotter, selected_scenarios, chart_type, breakdown, secondary_metric
        )
        return result if isinstance(result, go.Figure) else go.Figure(result)
