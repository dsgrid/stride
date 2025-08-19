from dash import Input, Output, callback

from stride.ui.plotting import StridePlots
from stride.ui.color_manager import ColorManager
from stride.api.utils import ConsumptionBreakdown, SecondaryMetric, ChartType
from typing import TYPE_CHECKING, Any, Literal
import plotly.graph_objects as go
from loguru import logger


if TYPE_CHECKING:
    from stride.api import APIClient
    from stride.ui.plotting import StridePlots
    from stride.ui.color_manager import ColorManager


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


def update_home_scenario_comparison(
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
        Secondary metric for right axis (not yet implemented)

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
        if secondary_metric:
            try:
                pass  # Placeholder
            except Exception as e:
                print(f"Secondary metric error: {e}")

        return fig

    except Exception as e:
        print(f"Error in update_home_scenario_comparison: {e}")
        import traceback

        traceback.print_exc()
        return {"data": [], "layout": {"title": f"Error: {str(e)}"}}


def update_home_sector_breakdown(
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
        Secondary metric for right axis (not yet implemented)

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
        if secondary_metric:
            try:
                pass  # Placeholder
            except Exception as e:
                print(f"Secondary metric error: {e}")

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
    selected_year: int,
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
    selected_year : int
        Selected year for load duration curve

    Returns
    -------
    go.Figure or dict
        Plotly figure object or empty dictionary if no data
    """
    if not selected_scenarios or not selected_year:
        return {}

    try:
        df = data_handler.get_load_duration_curve(
            years=selected_year, scenarios=selected_scenarios
        )
        return plotter.demand_curve(df)
    except Exception as e:
        logger.trace(e)
        return {}


def update_home_scenario_timeseries(
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
        Secondary metric for right axis (not yet implemented)

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

        # Create the faceted plot
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


def register_home_callbacks(
    data_handler: "APIClient",
    plotter: "StridePlots",
    scenarios: list[str],
    sectors: list[str],
    years: list[int],
    color_manager: "ColorManager",
) -> None:
    """
    Register all callbacks for the home module.

    Parameters
    ----------
    data_handler : APIClient
        API client for data access
    plotter : StridePlots
        Plotting utilities
    scenarios : list[str]
        List of available scenarios
    sectors : list[str]
        List of available sectors
    years : list[int]
        List of available years
    color_manager : ColorManager
        Color management utilities
    """

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
        [Input(input_id, "value") for input_id in home_input_ids],
        prevent_initial_call=True,
    )
    def _save_home_state_callback(*values: Any) -> dict[str, Any]:
        return save_home_state(*values)

    # Home tab callbacks
    @callback(
        Output("home-scenario-comparison", "figure"),
        Input("home-scenarios-checklist", "value"),
        Input("home-consumption-breakdown", "value"),
        Input("home-secondary-metric", "value"),
    )
    def _update_home_scenario_comparison_callback(
        selected_scenarios: list[str],
        breakdown: ConsumptionBreakdown | Literal["None"],
        secondary_metric: SecondaryMetric | Literal["None"],
    ) -> go.Figure | dict[str, Any]:
        return update_home_scenario_comparison(
            data_handler, plotter, selected_scenarios, breakdown, secondary_metric
        )

    @callback(
        Output("home-sector-breakdown", "figure"),
        Input("home-scenarios-2-checklist", "value"),
        Input("home-peak-breakdown", "value"),
        Input("home-peak-secondary-metric", "value"),
    )
    def _update_home_sector_breakdown_callback(
        selected_scenarios: list[str],
        breakdown: ConsumptionBreakdown | Literal["None"],
        secondary_metric: SecondaryMetric | Literal["None"],
    ) -> go.Figure | dict[str, Any]:
        return update_home_sector_breakdown(
            data_handler, plotter, selected_scenarios, breakdown, secondary_metric
        )

    @callback(
        Output("home-load-duration", "figure"),
        Input("home-scenarios-3-checklist", "value"),
        Input("home-year-dropdown", "value"),
    )
    def _update_home_load_duration_callback(
        selected_scenarios: list[str], selected_year: int
    ) -> go.Figure | dict[str, Any]:
        return update_home_load_duration(data_handler, plotter, selected_scenarios, selected_year)

    @callback(
        Output("home-scenario-timeseries", "figure"),
        Input("home-scenarios-4-checklist", "value"),
        Input("home-timeseries-chart-type", "value"),
        Input("home-timeseries-breakdown", "value"),
        Input("home-timeseries-secondary-metric", "value"),
    )
    def _update_home_scenario_timeseries_callback(
        selected_scenarios: list[str],
        chart_type: ChartType,
        breakdown: ConsumptionBreakdown | Literal["None"],
        secondary_metric: SecondaryMetric | Literal["None"],
    ) -> go.Figure | dict[str, Any]:
        return update_home_scenario_timeseries(
            data_handler, plotter, selected_scenarios, chart_type, breakdown, secondary_metric
        )
