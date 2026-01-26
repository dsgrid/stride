from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Literal

import plotly.graph_objects as go
from dash import Input, Output, State, callback
from dash.exceptions import PreventUpdate
from loguru import logger

from stride.api.utils import (
    ConsumptionBreakdown,
    ResampleOptions,
    SecondaryMetric,
    TimeGroup,
    TimeGroupAgg,
    WeatherVar,
)
from stride.ui.plotting.utils import get_error_annotation_style, get_neutral_color

if TYPE_CHECKING:
    from stride.api import APIClient
    from stride.ui.plotting import StridePlots


def get_secondary_metric_label(metric: str) -> str:
    """Get a formatted label with units for a secondary metric."""
    metric_labels = {
        "GDP": "GDP (Billion USD-2024)",
        "GDP Per Capita": "GDP Per Capita (USD-2024/person)",
    }
    return metric_labels.get(metric, metric)


def get_weather_label(weather_var: str) -> str:
    """Get a formatted label with units for a weather variable."""
    weather_labels = {
        "BAIT": "BAIT (deg C)",
        "HDD": "HDD (deg C)",
        "CDD": "CDD (deg C)",
    }
    return weather_labels.get(weather_var, weather_var)


def _add_weather_to_timeseries(
    fig: go.Figure,
    data_handler: "APIClient",
    plotter: "StridePlots",
    scenario: str,
    weather_var: WeatherVar,
    selected_years_int: list[int],
    resample: ResampleOptions,
) -> None:
    """
    Add weather variable traces to a timeseries plot.

    Parameters
    ----------
    fig : go.Figure
        Plotly figure to add weather traces to
    data_handler : APIClient
        API client for data access
    plotter : StridePlots
        Plotting utilities for creating charts
    scenario : str
        Selected scenario name
    weather_var : WeatherVar
        Weather variable to add
    selected_years_int : list[int]
        List of selected years
    resample : ResampleOptions
        Resampling option
    """
    try:
        for year in selected_years_int:
            # For hourly energy data, we need hourly weather data
            # But weather data is daily, so we need to repeat each value 24 times
            weather_resample = resample if resample != "Hourly" else "Daily Mean"

            weather_df = data_handler.get_weather_metric(
                scenario=scenario,
                year=year,
                wvar=weather_var,
                resample=weather_resample,
                timegroup=None,
            )

            if not weather_df.empty:
                weather_df = weather_df.copy()

                # If energy data is hourly, repeat each daily weather value 24 times
                if resample == "Hourly":
                    # Repeat each row 24 times
                    weather_df = weather_df.loc[weather_df.index.repeat(24)].reset_index(drop=True)

                # Convert to time_period indexing to match energy data
                # Time period is 1-indexed (1, 2, 3, ...)
                weather_df["time_period"] = range(1, len(weather_df) + 1)

                # Add weather variable as a line trace on the right y-axis
                fig.add_trace(
                    go.Scatter(
                        x=weather_df["time_period"],
                        y=weather_df["value"],
                        name=f"{year} - {weather_var}",
                        mode="lines",
                        yaxis="y2",
                        line=dict(width=1.5, dash="dot"),
                        customdata=weather_df["value"],
                        hovertemplate=f"{year} - {weather_var}: %{{customdata:.2f}}<extra></extra>",
                    )
                )

        # Update layout to add secondary y-axis for weather
        fig.update_layout(
            yaxis=dict(rangemode="tozero"),
            yaxis2=dict(
                title=get_weather_label(weather_var),
                overlaying="y",
                side="right",
            ),
            legend=dict(orientation="v", yanchor="top", y=1.0, xanchor="left", x=1.05),
        )
    except NotImplementedError as e:
        # Show error annotation for unsupported weather variables
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
            error_msg = f"Weather table not available for {weather_var}"

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
        logger.error(f"Weather variable error: {e}")


def update_summary_stats(
    data_handler: "APIClient", scenario: str, selected_year: int, start_year: int | None = None
) -> tuple[str, str, str, str]:
    """
    Update summary statistics for a given scenario and year.

    Parameters
    ----------
    data_handler : APIClient
        API client for data access
    scenario : str
        Selected scenario name
    selected_year : int
        Selected year for summary statistics
    start_year : int, optional
        Start year for CAGR calculation. If None, uses the first year in the dataset.

    Returns
    -------
    tuple[str, str, str, str]
        Tuple containing (annual_consumption, consumption_cagr, peak_demand, peak_demand_cagr) as formatted strings
    """

    years = data_handler.years

    if not selected_year or scenario not in data_handler.scenarios:
        return "---", "---", "---", "---"

    try:
        # Get all consumption and peak demand data for this scenario
        consumption_df = data_handler.get_annual_electricity_consumption(
            scenarios=[scenario], years=years
        )
        peak_demand_df = data_handler.get_annual_peak_demand(scenarios=[scenario], years=years)
        # Convert to dictionaries for fast lookup
        consumption_by_year = consumption_df.set_index("year")["value"].to_dict()
        peak_demand_by_year = peak_demand_df.set_index("year")["value"].to_dict()

        # Get values for selected year
        annual_consumption = consumption_by_year.get(selected_year, 0)
        peak_demand = peak_demand_by_year.get(selected_year, 0)

        # Use provided start year or default to first year
        sorted_years = sorted(years)
        if start_year is None:
            start_year = sorted_years[0]

        if selected_year == start_year:
            # Same year - no growth to calculate
            consumption_cagr = "N/A"
            peak_demand_cagr = "N/A"
        else:
            # Calculate CAGR: ((End Value / Start Value) ^ (1 / Number of Years)) - 1
            num_years = selected_year - start_year
            start_consumption = consumption_by_year.get(start_year, 0)
            start_peak_demand = peak_demand_by_year.get(start_year, 0)

            if start_consumption > 0 and annual_consumption > 0:
                consumption_cagr_value = (
                    (annual_consumption / start_consumption) ** (1 / num_years) - 1
                ) * 100
                consumption_cagr = f"{consumption_cagr_value:.2f}%"
            else:
                consumption_cagr = "N/A"

            if start_peak_demand > 0 and peak_demand > 0:
                peak_demand_cagr_value = (
                    (peak_demand / start_peak_demand) ** (1 / num_years) - 1
                ) * 100
                peak_demand_cagr = f"{peak_demand_cagr_value:.2f}%"
            else:
                peak_demand_cagr = "N/A"

        return (
            f"{annual_consumption:,.0f}",
            consumption_cagr,
            f"{peak_demand:,.0f}",
            peak_demand_cagr,
        )

    except Exception as e:
        print(f"Error calculating summary stats for {scenario}, year {selected_year}: {e}")
        return "Error", "Error", "Error", "Error"


def update_consumption_plot(
    data_handler: "APIClient",
    plotter: "StridePlots",
    scenario: str,
    breakdown: ConsumptionBreakdown | Literal["None"] | None,
    secondary_metric: SecondaryMetric | Literal["None"] | None,
) -> go.Figure | dict[str, Any]:
    """
    Update the annual electricity consumption plot.

    Parameters
    ----------
    data_handler : APIClient
        API client for data access
    plotter : StridePlots
        Plotting utilities for creating charts
    scenario : str
        Selected scenario name
    breakdown : ConsumptionBreakdown
        Breakdown type ("None", "Sector", or "End Use")
    secondary_metric : SecondaryMetric
        Secondary metric for right axis

    Returns
    -------
    go.Figure or dict
        Plotly figure object or error dictionary
    """

    if scenario not in data_handler.scenarios:
        logger.error(f"Error: {scenario} does not exist.")
        return {"data": [], "layout": {"title": f"Error: {scenario} does not exist."}}
    try:
        # Convert "None" to None
        breakdown_value = None if breakdown == "None" else breakdown
        # Get consumption data for this scenario
        df = data_handler.get_annual_electricity_consumption(
            scenarios=[scenario], group_by=breakdown_value
        )
        # Create plot
        if breakdown_value:
            stack_col = "metric" if breakdown_value == "End Use" else breakdown_value.lower()
            fig = plotter.grouped_stacked_bars(
                df,
                stack_col=stack_col,
                value_col="value",
                group_col="scenario",
                show_scenario_indicators=False,
            )
        else:
            # Use theme-aware neutral gray color for the bars
            neutral_color = get_neutral_color(plotter.get_template())
            fig = plotter.grouped_single_bars(df, "year", fixed_color=neutral_color)

        # Add secondary metric if selected
        if secondary_metric and secondary_metric != "None":
            try:
                secondary_df = data_handler.get_secondary_metric(
                    scenario=scenario, metric=secondary_metric, years=None
                )

                if not secondary_df.empty:
                    # Get scenario color from color manager
                    scenario_color = plotter.color_manager.get_color(scenario)

                    # Add secondary metric as a line trace on the right y-axis
                    fig.add_trace(
                        go.Scatter(
                            x=secondary_df["year"],
                            y=secondary_df["value"],
                            name=secondary_metric,
                            mode="lines+markers",
                            yaxis="y2",
                            line=dict(width=2, dash="dash", color=scenario_color),
                            marker=dict(size=6, color=scenario_color),
                            customdata=secondary_df["value"],
                            hovertemplate=f"{secondary_metric}: %{{customdata:.2f}}<extra></extra>",
                        )
                    )

                    # Update layout to add secondary y-axis
                    fig.update_layout(
                        yaxis=dict(title="Energy Consumption (MWh)"),
                        yaxis2=dict(
                            title=get_secondary_metric_label(secondary_metric),
                            overlaying="y",
                            side="right",
                        ),
                        legend=dict(orientation="v", yanchor="top", y=1.0, xanchor="left", x=1.05),
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
            fig.update_layout(yaxis=dict(title="Energy Consumption (MWh)"))

        return fig
    except Exception as e:
        logger.error(f"Error in consumption plot: {e}")
        return {"data": [], "layout": {"title": f"Error: {str(e)}"}}


def update_peak_plot(
    data_handler: "APIClient",
    plotter: "StridePlots",
    scenario: str,
    breakdown: ConsumptionBreakdown | Literal["None"] | None,
    secondary_metric: SecondaryMetric | Literal["None"] | None,
) -> go.Figure | dict[str, Any]:
    """
    Update the annual peak demand plot.

    Parameters
    ----------
    data_handler : APIClient
        API client for data access
    plotter : StridePlots
        Plotting utilities for creating charts
    scenario : str
        Selected scenario name
    breakdown : ConsumptionBreakdown
        Breakdown type ("None", "Sector", or "End Use")
    secondary_metric : SecondaryMetric
        Secondary metric for right axis

    Returns
    -------
    go.Figure or dict
        Plotly figure object or error dictionary
    """
    if scenario not in data_handler.scenarios:
        logger.error(f"Error: {scenario} does not exist.")
        return {"data": [], "layout": {"title": f"Error: {scenario} does not exist."}}
    try:
        # Convert "None" to None
        breakdown_value = None if breakdown == "None" else breakdown
        # Get peak demand data for this scenario
        df = data_handler.get_annual_peak_demand(scenarios=[scenario], group_by=breakdown_value)
        # Create plot
        if breakdown_value:
            stack_col = "metric" if breakdown_value == "End Use" else breakdown_value.lower()
            fig = plotter.grouped_stacked_bars(
                df,
                stack_col=stack_col,
                value_col="value",
                group_col="scenario",
                show_scenario_indicators=False,
            )
        else:
            # Use theme-aware neutral gray color for the bars
            neutral_color = get_neutral_color(plotter.get_template())
            fig = plotter.grouped_single_bars(df, "year", fixed_color=neutral_color)

        # Add secondary metric if selected
        if secondary_metric and secondary_metric != "None":
            try:
                secondary_df = data_handler.get_secondary_metric(
                    scenario=scenario, metric=secondary_metric, years=None
                )

                if not secondary_df.empty:
                    # Get scenario color from color manager
                    scenario_color = plotter.color_manager.get_color(scenario)

                    # Add secondary metric as a line trace on the right y-axis
                    fig.add_trace(
                        go.Scatter(
                            x=secondary_df["year"],
                            y=secondary_df["value"],
                            name=secondary_metric,
                            mode="lines+markers",
                            yaxis="y2",
                            line=dict(width=2, dash="dash", color=scenario_color),
                            marker=dict(size=6, color=scenario_color),
                            customdata=secondary_df["value"],
                            hovertemplate=f"{secondary_metric}: %{{customdata:.2f}}<extra></extra>",
                        )
                    )

                    # Update layout to add secondary y-axis
                    fig.update_layout(
                        yaxis=dict(title="Power Demand (MW)"),
                        yaxis2=dict(
                            title=get_secondary_metric_label(secondary_metric),
                            overlaying="y",
                            side="right",
                        ),
                        legend=dict(orientation="v", yanchor="top", y=1.0, xanchor="left", x=1.05),
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
        logger.error(f"Error in peak demand plot: {e}")
        return {"data": [], "layout": {"title": f"Error: {str(e)}"}}


def update_timeseries_plot(
    data_handler: "APIClient",
    plotter: "StridePlots",
    scenario: str,
    breakdown: ConsumptionBreakdown | Literal["None"] | None,
    resample: ResampleOptions,
    weather_var: WeatherVar | Literal["None"] | None,
    selected_years: int | list[int],
) -> go.Figure | dict[str, Any]:
    """
    Update the timeseries comparison plot for multiple years.

    Parameters
    ----------
    data_handler : APIClient
        API client for data access
    plotter : StridePlots
        Plotting utilities for creating charts
    scenario : str
        Selected scenario name
    breakdown : ConsumptionBreakdown
        Breakdown type ("None", "Sector", or "End Use")
    resample : ResampleOptions
        Resampling option ("Daily Mean" or "Weekly Mean")
    weather_var : WeatherVar | "None" | None
        Weather variable for secondary axis (not yet implemented)
    selected_years : list[int]
        List of selected years to display

    Returns
    -------
    go.Figure or dict
        Plotly figure object or error dictionary
    """

    if isinstance(selected_years, (int, str)):
        selected_years = [selected_years]

    if not selected_years or scenario not in data_handler.scenarios:
        return {"data": [], "layout": {"title": "Select years to view data"}}
    try:
        # Convert years to integers (UI may pass strings)
        selected_years_int = [int(year) for year in selected_years]

        # Convert "None" to None
        breakdown_value = None if breakdown == "None" else breakdown

        # Get timeseries data. Need to pass "End Use" Literal Hera
        df = data_handler.get_time_series_comparison(
            scenario=scenario,
            years=selected_years_int,
            group_by=breakdown_value,
            resample=resample,
        )
        # Need to assign to new variable for typing.
        stack_col = "metric" if breakdown_value == "End Use" else str(breakdown_value)
        # Use the new time_series function for better multi-year visualization
        fig = plotter.time_series(df, group_by=stack_col.lower() if breakdown_value else None)

        # Add weather variable if selected
        if weather_var and weather_var != "None":
            _add_weather_to_timeseries(
                fig, data_handler, plotter, scenario, weather_var, selected_years, resample
            )
        else:
            # No weather variable - just ensure y-axis starts at zero
            fig.update_yaxes(rangemode="tozero")

        return fig
    except Exception as e:
        print(f"Error in timeseries plot: {e}")
        return {"data": [], "layout": {"title": f"Error: {str(e)}"}}


def update_yearly_plot(  # noqa: C901
    data_handler: "APIClient",
    plotter: "StridePlots",
    scenario: str,
    breakdown: ConsumptionBreakdown | Literal["None"] | None,
    resample: ResampleOptions,
    weather_var: WeatherVar | Literal["None"] | None,
    selected_year: int | list[int],
) -> go.Figure | dict[str, Any]:
    """
    Update the yearly area plot for a single year.

    Parameters
    ----------
    data_handler : APIClient
        API client for data access
    plotter : StridePlots
        Plotting utilities for creating charts
    scenario : str
        Selected scenario name
    breakdown : ConsumptionBreakdown
        Breakdown type ("None", "Sector", or "End Use")
    resample : ResampleOptions
        Resampling option ("Daily Mean", "Weekly Mean", or "Hourly")
    weather_var : WeatherVar | "None" | None
        Weather variable for secondary axis (not yet implemented)
    selected_year : list[int]
        Selected year to display (should be single year)

    Returns
    -------
    go.Figure or dict
        Plotly figure object or error dictionary
    """

    if isinstance(selected_year, (int, str)):
        selected_year = [selected_year]

    if not selected_year or scenario not in data_handler.scenarios:
        return {"data": [], "layout": {"title": "Select a year to view data"}}
    try:
        # Convert years to integers (UI may pass strings)
        selected_year_int = [int(year) for year in selected_year]

        # Convert "None" to None
        breakdown_value = None if breakdown == "None" else breakdown
        # Get timeseries data for single year
        year_int = selected_year_int[0]
        df = data_handler.get_time_series_comparison(
            scenario=scenario, years=selected_year_int, group_by=breakdown_value, resample=resample
        )

        stack_col = "metric" if breakdown_value == "End Use" else str(breakdown_value)

        # Use the time_series function with area chart type
        fig = plotter.time_series(
            df, group_by=stack_col.lower() if breakdown_value else None, chart_type="Area"
        )

        # Ensure y-axis starts at zero
        fig.update_layout(yaxis=dict(rangemode="tozero"))

        # Add weather variable if selected
        if weather_var and weather_var != "None":
            try:
                # For hourly energy data, we need hourly weather data
                # But weather data is daily, so we need to repeat each value 24 times
                weather_resample = resample if resample != "Hourly" else "Daily Mean"

                weather_df = data_handler.get_weather_metric(
                    scenario=scenario,
                    year=year_int,
                    wvar=weather_var,
                    resample=weather_resample,
                    timegroup=None,
                )

                if not weather_df.empty:
                    weather_df = weather_df.copy()

                    # If energy data is hourly, repeat each daily weather value 24 times
                    if resample == "Hourly":
                        # Repeat each row 24 times
                        weather_df = weather_df.loc[weather_df.index.repeat(24)].reset_index(
                            drop=True
                        )

                    # Convert to time_period indexing to match energy data
                    # Time period is 1-indexed (1, 2, 3, ...)
                    weather_df["time_period"] = range(1, len(weather_df) + 1)

                    # Add weather variable as a line trace on the right y-axis
                    fig.add_trace(
                        go.Scatter(
                            x=weather_df["time_period"],
                            y=weather_df["value"],
                            name=weather_var,
                            mode="lines",
                            yaxis="y2",
                            line=dict(width=1.5, dash="dot"),
                            customdata=weather_df["value"],
                            hovertemplate=f"{weather_var}: %{{customdata:.2f}}<extra></extra>",
                        )
                    )

                    # Update layout to add secondary y-axis for weather
                    fig.update_layout(
                        yaxis2=dict(
                            title=get_weather_label(weather_var),
                            overlaying="y",
                            side="right",
                        ),
                        legend=dict(orientation="v", yanchor="top", y=1.0, xanchor="left", x=1.05),
                    )
            except NotImplementedError as e:
                # Show error annotation for unsupported weather variables
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
                    error_msg = f"Weather table not available for {weather_var}"

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
                logger.error(f"Weather variable error: {e}")

        return fig
    except Exception as e:
        print(f"Error in yearly plot: {e}")
        return {"data": [], "layout": {"title": f"Error: {str(e)}"}}


# NOTE, do we need to add an input for Years?
# Currently the user can just toggle a year on/off through the plotly output.
def update_seasonal_lines_plot(
    data_handler: "APIClient",
    plotter: "StridePlots",
    scenario: str,
    timegroup: TimeGroup,
    agg: TimeGroupAgg,
    weather_var: WeatherVar | Literal["None"] | None,
) -> go.Figure | dict[str, Any]:
    """
    Update the seasonal load lines plot.

    Parameters
    ----------
    data_handler : APIClient
        API client for data access
    plotter : StridePlots
        Plotting utilities for creating charts
    scenario : str
        Selected scenario name
    timegroup : TimeGroup
        Time grouping option ("Seasonal", "Weekday/Weekend", or "Seasonal and Weekday/Weekend")
    agg : TimeGroupAgg
        Aggregation method ("Average Day", "Peak Day", "Minimum Day", or "Median Day")
    weather_var : WeatherVar
        Weather variable for secondary axis (not currently supported for seasonal plots)

    Returns
    -------
    go.Figure or dict
        Plotly figure object or error dictionary
    """

    if scenario not in data_handler.scenarios:
        return {"data": [], "layout": {"title": f"Error: {str(scenario)} not found"}}
    try:
        # Get seasonal load lines data
        df = data_handler.get_seasonal_load_lines(
            scenario=scenario,
            years=data_handler.years,  # Use all available years
            group_by=timegroup,
            agg=agg,
        )
        # Use the new seasonal_load_lines plotting method
        fig = plotter.seasonal_load_lines(df)
        return fig
    except Exception as e:
        print(f"Error in seasonal lines plot: {e}")
        return {"data": [], "layout": {"title": f"Error: {str(e)}"}}


def update_seasonal_area_plot(
    data_handler: "APIClient",
    plotter: "StridePlots",
    scenario: str,
    breakdown: ConsumptionBreakdown | Literal["None"] | None,
    selected_year: int,
    timegroup: TimeGroup,
    agg: TimeGroupAgg,
    weather_var: WeatherVar | Literal["None"] | None,
) -> go.Figure | dict[str, Any]:
    """
    Update the seasonal load area plot with optional breakdown.

    Parameters
    ----------
    data_handler : APIClient
        API client for data access
    plotter : StridePlots
        Plotting utilities for creating charts
    scenario : str
        Selected scenario name
    breakdown : ConsumptionBreakdown
        Breakdown type ("None", "Sector", or "End Use")
    selected_year : int
        Selected year to display
    timegroup : TimeGroup
        Time grouping option ("Seasonal", "Weekday/Weekend", or "Seasonal and Weekday/Weekend")
    agg : TimeGroupAgg
        Aggregation method ("Average Day", "Peak Day", "Minimum Day", or "Median Day")
    weather_var : WeatherVar | "None" | None
        Weather variable for secondary axis (not yet implemented)

    Returns
    -------
    go.Figure or dict
        Plotly figure object or error dictionary
    """

    if not selected_year or scenario not in data_handler.scenarios:
        return {"data": [], "layout": {"title": "Select a year to view data"}}
    try:
        # Convert "None" to None
        breakdown_value = None if breakdown == "None" else breakdown
        # Get seasonal load data with breakdown
        df = data_handler.get_seasonal_load_area(
            scenario=scenario,
            year=selected_year,
            group_by=timegroup,
            agg=agg,
            breakdown=breakdown_value,
        )
        # Create area plot using the new seasonal_load_area method
        fig = plotter.seasonal_load_area(df)
        return fig
    except Exception as e:
        print(f"Error in seasonal area plot: {e}")
        return {"data": [], "layout": {"title": f"Error: {str(e)}"}}


def update_load_duration_plot(
    data_handler: "APIClient",
    plotter: "StridePlots",
    scenario: str,
    selected_years: int | list[int],
) -> go.Figure | dict[str, Any]:
    """
    Update the load duration curve plot.

    Parameters
    ----------
    data_handler : APIClient
        API client for data access
    plotter : StridePlots
        Plotting utilities for creating charts
    scenario : str
        Selected scenario name
    selected_years : list[int]
        List of selected years to display

    Returns
    -------
    go.Figure or dict
        Plotly figure object or error dictionary
    """

    if isinstance(selected_years, int):
        selected_years = [selected_years]

    if not selected_years or scenario not in data_handler.scenarios:
        return {"data": [], "layout": {"title": "Select years to view data"}}
    try:
        # Convert years to int
        selected_years_int = [int(year) for year in selected_years]
        # Get load duration curve data
        df = data_handler.get_load_duration_curve(years=selected_years_int, scenarios=[scenario])
        return plotter.demand_curve(df)
    except Exception as e:
        print(f"Error in load duration plot: {e}")
        return {"data": [], "layout": {"title": f"Error: {str(e)}"}}


def _register_summary_callbacks(  # noqa: C901
    get_data_handler_func: Callable[[], "APIClient | None"],
    get_plotter_func: Callable[[], "StridePlots | None"],
) -> None:
    """Register summary statistics callbacks."""

    @callback(
        [
            Output("scenario-summary-start-year", "options"),
            Output("scenario-summary-start-year", "value"),
        ],
        [Input("scenario-summary-year", "value")],
        [State("scenario-summary-start-year", "value")],
    )
    def _update_start_year_options(
        selected_year: int, current_start_year: int | None
    ) -> tuple[list[dict[str, Any]], int]:
        """Update start year dropdown to only show years <= selected year, preserving current value if valid."""
        data_handler = get_data_handler_func()
        if data_handler is None:
            raise PreventUpdate

        if not selected_year:
            years = data_handler.years
            return [{"label": str(year), "value": year} for year in years], years[0]

        # Filter years to only those <= selected_year
        valid_years = [year for year in data_handler.years if year <= selected_year]
        options = [{"label": str(year), "value": year} for year in valid_years]

        # If current start year is still valid, keep it; otherwise default to first year
        if current_start_year is not None and current_start_year in valid_years:
            default_value = current_start_year
        else:
            default_value = valid_years[0] if valid_years else selected_year

        return options, default_value

    @callback(
        [
            Output("scenario-total-consumption", "children"),
            Output("scenario-consumption-cagr", "children"),
            Output("scenario-peak-demand", "children"),
            Output("scenario-peak-demand-cagr", "children"),
        ],
        [
            Input("view-selector", "value"),
            Input("scenario-summary-year", "value"),
            Input("scenario-summary-start-year", "value"),
        ],
    )
    def _update_summary_stats_callback(
        scenario: str, selected_year: int, start_year: int
    ) -> tuple[str, str, str, str]:
        data_handler = get_data_handler_func()
        if data_handler is None:
            raise PreventUpdate
        # "compare" is the Home tab, not a scenario
        if scenario == "compare":
            raise PreventUpdate
        return update_summary_stats(data_handler, scenario, selected_year, start_year)

    @callback(Output("scenario-title", "children"), Input("view-selector", "value"))
    def _update_scenario_title(selected_view: str) -> str:
        data_handler = get_data_handler_func()
        if data_handler is None:
            return "Scenario"
        scenarios = data_handler.scenarios  # Get from data_handler
        if selected_view in scenarios:
            return f"{selected_view}"
        # TODO make literal of Scenario or Home
        return "Scenario"


def _register_consumption_callbacks(
    get_data_handler_func: Callable[[], "APIClient | None"],
    get_plotter_func: Callable[[], "StridePlots | None"],
) -> None:
    """Register consumption and peak demand callbacks."""

    @callback(
        Output("scenario-consumption-plot", "figure"),
        [
            Input("view-selector", "value"),
            Input("scenario-consumption-breakdown", "value"),
            Input("scenario-consumption-secondary", "value"),
            Input("chart-refresh-trigger", "data"),
        ],
    )
    def _update_consumption_plot_callback(
        scenario: str,
        breakdown: ConsumptionBreakdown | Literal["None"],
        secondary_metric: SecondaryMetric | Literal["None"],
        refresh_trigger: int,
    ) -> go.Figure | dict[str, Any]:
        data_handler = get_data_handler_func()
        plotter = get_plotter_func()
        if data_handler is None or plotter is None:
            raise PreventUpdate
        # "compare" is the Home tab, not a scenario
        if scenario == "compare":
            raise PreventUpdate
        return update_consumption_plot(
            data_handler, plotter, scenario, breakdown, secondary_metric
        )

    @callback(
        Output("scenario-peak-plot", "figure"),
        [
            Input("view-selector", "value"),
            Input("scenario-peak-breakdown", "value"),
            Input("scenario-peak-secondary", "value"),
            Input("chart-refresh-trigger", "data"),
        ],
    )
    def _update_peak_plot_callback(
        scenario: str,
        breakdown: ConsumptionBreakdown | Literal["None"],
        secondary_metric: SecondaryMetric | Literal["None"],
        refresh_trigger: int,
    ) -> go.Figure | dict[str, Any]:
        data_handler = get_data_handler_func()
        plotter = get_plotter_func()
        if data_handler is None or plotter is None:
            raise PreventUpdate
        # "compare" is the Home tab, not a scenario
        if scenario == "compare":
            raise PreventUpdate
        return update_peak_plot(data_handler, plotter, scenario, breakdown, secondary_metric)


def _register_timeseries_callbacks(
    get_data_handler_func: Callable[[], "APIClient | None"],
    get_plotter_func: Callable[[], "StridePlots | None"],
) -> None:
    """Register timeseries and yearly plot callbacks."""

    @callback(
        Output("scenario-timeseries-plot", "figure"),
        [
            Input("view-selector", "value"),
            Input("scenario-timeseries-breakdown", "value"),
            Input("scenario-timeseries-resample", "value"),
            Input("scenario-timeseries-weather", "value"),
            Input("scenario-timeseries-years", "value"),
            Input("chart-refresh-trigger", "data"),
        ],
    )
    def _update_timeseries_plot_callback(
        scenario: str,
        breakdown: ConsumptionBreakdown | Literal["None"],
        resample: str,
        weather_var: str | None,
        selected_years: list[int] | int,
        refresh_trigger: int,
    ) -> go.Figure | dict[str, Any]:
        data_handler = get_data_handler_func()
        plotter = get_plotter_func()
        if data_handler is None or plotter is None:
            raise PreventUpdate
        # "compare" is the Home tab, not a scenario
        if scenario == "compare":
            raise PreventUpdate
        return update_timeseries_plot(
            data_handler,
            plotter,
            scenario,
            breakdown,
            resample,  # type: ignore[arg-type]
            weather_var,  # type: ignore[arg-type]
            selected_years,
        )

    @callback(
        Output("scenario-yearly-plot", "figure"),
        [
            Input("view-selector", "value"),
            Input("scenario-yearly-breakdown", "value"),
            Input("scenario-yearly-resample", "value"),
            Input("scenario-yearly-weather", "value"),
            Input("scenario-yearly-year", "value"),
            Input("chart-refresh-trigger", "data"),
        ],
    )
    def _update_yearly_plot_callback(
        scenario: str,
        breakdown: ConsumptionBreakdown | Literal["None"],
        resample: str,
        weather_var: str | None,
        selected_year: int,
        refresh_trigger: int,
    ) -> go.Figure | dict[str, Any]:
        data_handler = get_data_handler_func()
        plotter = get_plotter_func()
        if data_handler is None or plotter is None:
            raise PreventUpdate
        # "compare" is the Home tab, not a scenario
        if scenario == "compare":
            raise PreventUpdate
        return update_yearly_plot(
            data_handler,
            plotter,
            scenario,
            breakdown,
            resample,  # type: ignore[arg-type]
            weather_var,  # type: ignore[arg-type]
            selected_year,
        )


def _register_seasonal_callbacks(
    get_data_handler_func: Callable[[], "APIClient | None"],
    get_plotter_func: Callable[[], "StridePlots | None"],
) -> None:
    """Register seasonal plot callbacks."""

    @callback(
        Output("scenario-seasonal-lines-plot", "figure"),
        [
            Input("view-selector", "value"),
            Input("scenario-seasonal-lines-timegroup", "value"),
            Input("scenario-seasonal-lines-agg", "value"),
            Input("scenario-seasonal-lines-weather", "value"),
            Input("chart-refresh-trigger", "data"),
        ],
    )
    def _update_seasonal_lines_plot_callback(
        scenario: str,
        timegroup: str,
        agg_func: str,
        weather_var: WeatherVar | Literal["None"] | None,
        refresh_trigger: int,
    ) -> go.Figure | dict[str, Any]:
        data_handler = get_data_handler_func()
        plotter = get_plotter_func()
        if data_handler is None or plotter is None:
            raise PreventUpdate
        # "compare" is the Home tab, not a scenario
        if scenario == "compare":
            raise PreventUpdate
        return update_seasonal_lines_plot(
            data_handler,
            plotter,
            scenario,
            timegroup,  # type: ignore[arg-type]
            agg_func,  # type: ignore[arg-type]
            weather_var,
        )

    @callback(
        Output("scenario-seasonal-area-plot", "figure"),
        [
            Input("view-selector", "value"),
            Input("scenario-seasonal-area-breakdown", "value"),
            Input("scenario-seasonal-area-year", "value"),
            Input("scenario-seasonal-area-agg", "value"),
            Input("scenario-seasonal-area-timegroup", "value"),
            Input("scenario-seasonal-area-weather", "value"),
            Input("chart-refresh-trigger", "data"),
        ],
    )
    def _update_seasonal_area_plot_callback(
        scenario: str,
        breakdown: ConsumptionBreakdown | Literal["None"],
        selected_year: int,
        agg: TimeGroupAgg,
        timegroup: TimeGroup,
        weather_var: WeatherVar | Literal["None"] | None,
        refresh_trigger: int,
    ) -> go.Figure | dict[str, Any]:
        data_handler = get_data_handler_func()
        plotter = get_plotter_func()
        if data_handler is None or plotter is None:
            raise PreventUpdate
        # "compare" is the Home tab, not a scenario
        if scenario == "compare":
            raise PreventUpdate
        return update_seasonal_area_plot(
            data_handler, plotter, scenario, breakdown, selected_year, timegroup, agg, weather_var
        )


def _register_load_duration_callbacks(
    get_data_handler_func: Callable[[], "APIClient | None"],
    get_plotter_func: Callable[[], "StridePlots | None"],
) -> None:
    """Register load duration curve callbacks."""

    @callback(
        Output("scenario-load-duration-plot", "figure"),
        [
            Input("view-selector", "value"),
            Input("scenario-load-duration-years", "value"),
            Input("chart-refresh-trigger", "data"),
        ],
    )
    def _update_load_duration_plot_callback(
        scenario: str, selected_years: list[int] | int, refresh_trigger: int
    ) -> go.Figure | dict[str, Any]:
        data_handler = get_data_handler_func()
        plotter = get_plotter_func()
        if data_handler is None or plotter is None:
            raise PreventUpdate
        # "compare" is the Home tab, not a scenario
        if scenario == "compare":
            raise PreventUpdate
        return update_load_duration_plot(data_handler, plotter, scenario, selected_years)


def _register_state_callback() -> None:
    """Register state management callback."""
    scenario_input_ids = [
        "scenario-summary-year",
        "scenario-consumption-breakdown",
        "scenario-consumption-secondary",
        "scenario-peak-breakdown",
        "scenario-peak-secondary",
        "scenario-timeseries-breakdown",
        "scenario-timeseries-resample",
        "scenario-timeseries-weather",
        "scenario-timeseries-years",
        "scenario-yearly-breakdown",
        "scenario-yearly-resample",
        "scenario-yearly-weather",
        "scenario-yearly-year",
        "scenario-seasonal-lines-timegroup",
        "scenario-seasonal-lines-agg",
        "scenario-seasonal-lines-weather",
        "scenario-seasonal-area-breakdown",
        "scenario-seasonal-area-year",
        "scenario-seasonal-area-agg",
        "scenario-seasonal-area-timegroup",
        "scenario-seasonal-area-weather",
        "scenario-load-duration-years",
    ]

    @callback(
        Output("scenario-state-store", "data"),
        [Input(input_id, "value") for input_id in scenario_input_ids],
        prevent_initial_call=True,
    )
    def _save_scenario_state(*values: Any) -> dict[str, Any]:
        return dict(zip(scenario_input_ids, values))


def register_scenario_callbacks(
    get_data_handler_func: Callable[[], "APIClient | None"],
    get_plotter_func: Callable[[], "StridePlots | None"],
) -> None:
    """
    Register all callbacks for the single scenario view.

    Parameters
    ----------
    get_data_handler_func : Callable[[], APIClient | None]
        Function that returns the current APIClient instance
    get_plotter_func : Callable[[], StridePlots | None]
        Function that returns the current StridePlots instance
    """
    _register_state_callback()
    _register_summary_callbacks(get_data_handler_func, get_plotter_func)
    _register_consumption_callbacks(get_data_handler_func, get_plotter_func)
    _register_timeseries_callbacks(get_data_handler_func, get_plotter_func)
    _register_seasonal_callbacks(get_data_handler_func, get_plotter_func)
    _register_load_duration_callbacks(get_data_handler_func, get_plotter_func)
