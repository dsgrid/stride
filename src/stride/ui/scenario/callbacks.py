from typing import TYPE_CHECKING, Any, Literal

import plotly.graph_objects as go
from dash import Input, Output, callback
from loguru import logger

from stride.api.utils import (
    ConsumptionBreakdown,
    ResampleOptions,
    SecondaryMetric,
    TimeGroup,
    TimeGroupAgg,
    WeatherVar,
)

if TYPE_CHECKING:
    from stride.api import APIClient
    from stride.ui.plotting import StridePlots


def update_summary_stats(
    data_handler: "APIClient", scenario: str, selected_year: int
) -> tuple[str, str, str]:
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

    Returns
    -------
    tuple[str, str, str]
        Tuple containing (total_consumption, percent_growth, peak_demand) as formatted strings
    """

    years = data_handler.years

    if not selected_year or scenario not in data_handler.scenarios:
        return "---", "---", "---"

    try:
        # Get all consumption and peak demand data for this scenario
        consumption_df = data_handler.get_annual_electricity_consumption(
            scenarios=[scenario], years=years
        )
        peak_demand_df = data_handler.get_annual_peak_demand(scenarios=[scenario], years=years)
        # Convert to dictionaries for fast lookup
        consumption_by_year = consumption_df.set_index("year")["value"].to_dict()
        peak_demand_by_year = peak_demand_df.set_index("year")["value"].to_dict()
        # Get total consumption for selected year
        total_consumption = consumption_by_year.get(selected_year, 0)
        # Calculate percent growth compared to previous year
        if selected_year == min(years):
            # First year - no previous year to compare
            percent_growth = "N/A"
        else:
            # Find previous year in the sorted years list
            sorted_years = sorted(years)
            current_index = sorted_years.index(selected_year)
            if current_index > 0:
                previous_year = sorted_years[current_index - 1]
                previous_consumption = consumption_by_year.get(previous_year, 0)
                if previous_consumption > 0:
                    growth = (
                        (total_consumption - previous_consumption) / previous_consumption
                    ) * 100
                    percent_growth = f"{growth:.1f}"
                else:
                    percent_growth = "N/A"
            else:
                percent_growth = "N/A"
        # Get peak demand for selected year
        peak_demand = peak_demand_by_year.get(selected_year, 0)
        return (f"{total_consumption / 1e12:.1f}", percent_growth, f"{peak_demand / 1e6:,.0f}")

    except Exception as e:
        print(f"Error calculating summary stats for {scenario}, year {selected_year}: {e}")
        return "Error", "Error", "Error"


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
        Secondary metric for right axis (not yet implemented)

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
                df, stack_col=stack_col, value_col="value", group_col="scenario"
            )
        else:
            fig = plotter.grouped_single_bars(df, "year", use_color_manager=False)
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
        Secondary metric for right axis (not yet implemented)

    Returns
    -------
    go.Figure or dict
        Plotly figure object or error dictionary
    """

    if scenario not in data_handler.scenarios:
        return {"data": [], "layout": {"title": f"Error: {str(scenario)} not found"}}
    try:
        # Convert "None" to None
        breakdown_value = None if breakdown == "None" else breakdown
        # Get peak demand data for this scenario
        df = data_handler.get_annual_peak_demand(scenarios=[scenario], group_by=breakdown_value)
        # Create plot
        if breakdown_value:
            stack_col = "metric" if breakdown_value == "End Use" else breakdown_value.lower()
            fig = plotter.grouped_stacked_bars(
                df, stack_col=stack_col, value_col="value", group_col="scenario"
            )
        else:
            fig = plotter.grouped_single_bars(df, "year", use_color_manager=False)
        return fig

    except Exception as e:
        print(f"Error in peak plot: {e}")
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

    if isinstance(selected_years, int):
        selected_years = [selected_years]

    if not selected_years or scenario not in data_handler.scenarios:
        return {"data": [], "layout": {"title": "Select years to view data"}}
    try:
        # Convert "None" to None and years to int
        breakdown_value = None if breakdown == "None" else breakdown

        selected_years_int = [int(year) for year in selected_years]
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
        return fig
    except Exception as e:
        print(f"Error in timeseries plot: {e}")
        return {"data": [], "layout": {"title": f"Error: {str(e)}"}}


def update_yearly_plot(
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

    if isinstance(selected_year, int):
        selected_year = [selected_year]

    if not selected_year or scenario not in data_handler.scenarios:
        return {"data": [], "layout": {"title": "Select a year to view data"}}
    try:
        # Convert "None" to None
        breakdown_value = None if breakdown == "None" else breakdown
        # Get timeseries data for single year
        df = data_handler.get_time_series_comparison(
            scenario=scenario, years=selected_year, group_by=breakdown_value, resample=resample
        )

        stack_col = "metric" if breakdown_value == "End Use" else str(breakdown_value)

        # Use the time_series function with area chart type
        fig = plotter.time_series(
            df, group_by=stack_col.lower() if breakdown_value else None, chart_type="Area"
        )
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
        Weather variable for secondary axis (not yet implemented)

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


def _register_summary_callbacks(data_handler: "APIClient", plotter: "StridePlots") -> None:
    """Register summary statistics callbacks."""

    @callback(
        [
            Output("scenario-total-consumption", "children"),
            Output("scenario-percent-growth", "children"),
            Output("scenario-peak-demand", "children"),
        ],
        [Input("view-selector", "value"), Input("scenario-summary-year", "value")],
    )
    def _update_summary_stats_callback(scenario: str, selected_year: int) -> tuple[str, str, str]:
        return update_summary_stats(data_handler, scenario, selected_year)

    @callback(Output("scenario-title", "children"), Input("view-selector", "value"))
    def _update_scenario_title(selected_view: str) -> str:
        scenarios = data_handler.scenarios  # Get from data_handler
        if selected_view in scenarios:
            return f"{selected_view}"
        # TODO make literal of Scenario or Home
        return "Scenario"


def _register_consumption_callbacks(data_handler: "APIClient", plotter: "StridePlots") -> None:
    """Register consumption and peak demand callbacks."""

    @callback(
        Output("scenario-consumption-plot", "figure"),
        [
            Input("view-selector", "value"),
            Input("scenario-consumption-breakdown", "value"),
            Input("scenario-consumption-secondary", "value"),
        ],
    )
    def _update_consumption_plot_callback(
        scenario: str,
        breakdown: ConsumptionBreakdown | Literal["None"],
        secondary_metric: SecondaryMetric | Literal["None"],
    ) -> go.Figure | dict[str, Any]:
        return update_consumption_plot(
            data_handler, plotter, scenario, breakdown, secondary_metric
        )

    @callback(
        Output("scenario-peak-plot", "figure"),
        [
            Input("view-selector", "value"),
            Input("scenario-peak-breakdown", "value"),
            Input("scenario-peak-secondary", "value"),
        ],
    )
    def _update_peak_plot_callback(
        scenario: str,
        breakdown: ConsumptionBreakdown | Literal["None"],
        secondary_metric: SecondaryMetric | Literal["None"],
    ) -> go.Figure | dict[str, Any]:
        return update_peak_plot(data_handler, plotter, scenario, breakdown, secondary_metric)


def _register_timeseries_callbacks(data_handler: "APIClient", plotter: "StridePlots") -> None:
    """Register timeseries and yearly plot callbacks."""

    @callback(
        Output("scenario-timeseries-plot", "figure"),
        [
            Input("view-selector", "value"),
            Input("scenario-timeseries-breakdown", "value"),
            Input("scenario-timeseries-resample", "value"),
            Input("scenario-timeseries-weather", "value"),
            Input("scenario-timeseries-years", "value"),
        ],
    )
    def _update_timeseries_plot_callback(
        scenario: str,
        breakdown: ConsumptionBreakdown | Literal["None"],
        resample: ResampleOptions,
        weather_var: WeatherVar | Literal["None"] | None,
        selected_years: list[int] | int,
    ) -> go.Figure | dict[str, Any]:
        return update_timeseries_plot(
            data_handler, plotter, scenario, breakdown, resample, weather_var, selected_years
        )

    @callback(
        Output("scenario-yearly-plot", "figure"),
        [
            Input("view-selector", "value"),
            Input("scenario-yearly-breakdown", "value"),
            Input("scenario-yearly-resample", "value"),
            Input("scenario-yearly-weather", "value"),
            Input("scenario-yearly-year", "value"),
        ],
    )
    def _update_yearly_plot_callback(
        scenario: str,
        breakdown: ConsumptionBreakdown | Literal["None"],
        resample: ResampleOptions,
        weather_var: WeatherVar | Literal["None"] | None,
        selected_year: int,
    ) -> go.Figure | dict[str, Any]:
        return update_yearly_plot(
            data_handler, plotter, scenario, breakdown, resample, weather_var, selected_year
        )


def _register_seasonal_callbacks(data_handler: "APIClient", plotter: "StridePlots") -> None:
    """Register seasonal plot callbacks."""

    @callback(
        Output("scenario-seasonal-lines-plot", "figure"),
        [
            Input("view-selector", "value"),
            Input("scenario-seasonal-lines-timegroup", "value"),
            Input("scenario-seasonal-lines-agg", "value"),
            Input("scenario-seasonal-lines-weather", "value"),
        ],
    )
    def _update_seasonal_lines_plot_callback(
        scenario: str,
        timegroup: TimeGroup,
        agg: TimeGroupAgg,
        weather_var: WeatherVar | Literal["None"] | None,
    ) -> go.Figure | dict[str, Any]:
        return update_seasonal_lines_plot(
            data_handler, plotter, scenario, timegroup, agg, weather_var
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
        ],
    )
    def _update_seasonal_area_plot_callback(
        scenario: str,
        breakdown: ConsumptionBreakdown | Literal["None"],
        selected_year: int,
        agg: TimeGroupAgg,
        timegroup: TimeGroup,
        weather_var: WeatherVar | Literal["None"] | None,
    ) -> go.Figure | dict[str, Any]:
        return update_seasonal_area_plot(
            data_handler, plotter, scenario, breakdown, selected_year, timegroup, agg, weather_var
        )


def _register_load_duration_callbacks(data_handler: "APIClient", plotter: "StridePlots") -> None:
    """Register load duration curve callbacks."""

    @callback(
        Output("scenario-load-duration-plot", "figure"),
        [Input("view-selector", "value"), Input("scenario-load-duration-years", "value")],
    )
    def _update_load_duration_plot_callback(
        scenario: str, selected_years: list[int] | int
    ) -> go.Figure | dict[str, Any]:
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
    scenarios: list[str], years: list[int], data_handler: "APIClient", plotter: "StridePlots"
) -> None:
    """
    Register all callbacks for the single scenario view.

    Parameters
    ----------
    scenarios : list[str]
        List of all available scenarios
    years : list[int]
        Available years in the project
    data_handler : 'APIClient'
        API client for data access
    plotter : 'StridePlots'
        Plotting utilities
    """
    _register_state_callback()
    _register_summary_callbacks(data_handler, plotter)
    _register_consumption_callbacks(data_handler, plotter)
    _register_timeseries_callbacks(data_handler, plotter)
    _register_seasonal_callbacks(data_handler, plotter)
    _register_load_duration_callbacks(data_handler, plotter)
