from dash import html, dcc, Input, Output, callback
import dash_bootstrap_components as dbc
from stride.ui.plotting import StridePlots
from stride.api import (
    APIClient,
    literal_to_list,
    ConsumptionBreakdown,
    SecondaryMetric,
    ResampleOptions,
    WeatherVar,
    TimeGroup,
    TimeGroupAgg
)
from stride.ui.color_manager import ColorManager


def create_scenario_layout(scenario: str, years: list[int], data_handler: APIClient, color_manager: ColorManager, stored_state: dict = None):
    """
    Create the layout for an individual scenario tab based on scenario_tab_design.md.

    Parameters
    ----------
    scenario : str
        The scenario name
    years : list[int]
        Available years in the project
    data_handler : APIClient
        API client for data access
    color_manager : ColorManager
        Color manager for consistent styling
    stored_state : dict
        Optional; stored state for restoring previous selections

    Returns
    -------
    html.Div
        The complete scenario tab layout
    """

    # Get stored values or use defaults
    stored_state = stored_state or {}

    # Generate scenario CSS from ColorManager
    scenario_css = color_manager.generate_scenario_css()

    def create_styled_checklist(items_list, checklist_id, default_selection=None):
        """Create a styled checklist similar to home tab"""
        # Get stored value or use default
        stored_value = stored_state.get(checklist_id, default_selection if default_selection else items_list)

        return html.Div([
            # Add scenario-specific CSS styles
            html.Div([
                html.Script(f"""
                var style = document.createElement('style');
                style.textContent = `{scenario_css}`;
                document.head.appendChild(style);
                """)
            ]),
            dbc.Checklist(
                id=checklist_id,
                options=[{"label": item, "value": item} for item in items_list],
                value=stored_value,
                inline=True,
                className="scenario-checklist"
            )
        ])

    # Create summary stat card helper
    def create_summary_stat_card(stat_id, title):
        """Create a summary statistic card"""
        return dbc.Card([
            dbc.CardBody([
                html.H2(id=stat_id, className="text-center mb-2", style={"color": "#007bff", "fontWeight": "bold"}),
                html.P(title, className="text-center mb-0", style={"fontSize": "0.9rem", "fontWeight": "500"})
            ], className="py-3")
        ], className="h-100")

    return html.Div([
        # Header
        html.H2(f"{scenario}", className="mb-4 scenario-title"),

        # Summary Stats Section
        dbc.Card([
            dbc.CardHeader([
                dbc.Row([
                    dbc.Col([
                        html.H4("Summary Stats", className="mb-0")
                    ], width=3),
                    dbc.Col([
                        html.Label("Year:", style={"fontWeight": "bold", "fontSize": "0.9em"}),
                        dcc.Dropdown(
                            id=f"scenario-{scenario}-summary-year",
                            options=[{"label": str(year), "value": year} for year in years],
                            value=stored_state.get(f"scenario-{scenario}-summary-year", years[-1] if years else None),
                            clearable=False
                        )
                    ], width=3)
                ], align="center")
            ]),
            dbc.CardBody([
                dbc.Row([
                    dbc.Col([
                        create_summary_stat_card(f"scenario-{scenario}-total-consumption", "Total Consumption (TWh)")
                    ], width=4),
                    dbc.Col([
                        create_summary_stat_card(f"scenario-{scenario}-percent-growth", "Percent Growth (%)")
                    ], width=4),
                    dbc.Col([
                        create_summary_stat_card(f"scenario-{scenario}-peak-demand", "Peak Demand (MW)")
                    ], width=4)
                ])
            ])
        ], className="mb-4"),

        # Annual Energy Consumption
        dbc.Card([
            dbc.CardHeader([
                dbc.Row([
                    dbc.Col([
                        html.H4("Annual Energy Consumption", className="mb-0")
                    ], width=3),
                    dbc.Col([
                        html.Label("LEFT AXIS:", style={"fontWeight": "bold", "fontSize": "0.9em"}),
                        dcc.Dropdown(
                            id=f"scenario-{scenario}-consumption-breakdown",
                            options=[
                                {"label": "Annual Energy Consumption", "value": "None"},
                                {"label": "Annual Energy Consumption by Sector", "value": "Sector"},
                                {"label": "Annual Energy Consumption by End Use", "value": "End Use"}
                            ],
                            value=stored_state.get(f"scenario-{scenario}-consumption-breakdown", "None"),
                            clearable=False
                        )
                    ], width=4),
                    dbc.Col([
                        html.Label("RIGHT AXIS (Optional):", style={"fontWeight": "bold", "fontSize": "0.9em"}),
                        dcc.Dropdown(
                            id=f"scenario-{scenario}-consumption-secondary",
                            options=[{"label": val, "value": val} for val in literal_to_list(SecondaryMetric)],
                            value=stored_state.get(f"scenario-{scenario}-consumption-secondary", None),
                            clearable=True,
                            placeholder="Select secondary metric..."
                        )
                    ], width=5)
                ], align="center")
            ]),
            dbc.CardBody([
                dcc.Graph(id=f"scenario-{scenario}-consumption-plot")
            ])
        ], className="mb-4"),

        # Peak Demand
        dbc.Card([
            dbc.CardHeader([
                dbc.Row([
                    dbc.Col([
                        html.H4("Peak Energy Demand", className="mb-0")
                    ], width=3),
                    dbc.Col([
                        html.Label("LEFT AXIS:", style={"fontWeight": "bold", "fontSize": "0.9em"}),
                        dcc.Dropdown(
                            id=f"scenario-{scenario}-peak-breakdown",
                            options=[
                                {"label": "Annual Peak Demand", "value": "None"},
                                {"label": "Annual Peak Demand by Sector", "value": "Sector"},
                                {"label": "Annual Peak Demand by End Use", "value": "End Use"}
                            ],
                            value="None",
                            clearable=False
                        )
                    ], width=4),
                    dbc.Col([
                        html.Label("RIGHT AXIS (Optional):", style={"fontWeight": "bold", "fontSize": "0.9em"}),
                        dcc.Dropdown(
                            id=f"scenario-{scenario}-peak-secondary",
                            options=[{"label": val, "value": val} for val in literal_to_list(SecondaryMetric)],
                            value=None,
                            clearable=True,
                            placeholder="Select secondary metric..."
                        )
                    ], width=5)
                ], align="center")
            ]),
            dbc.CardBody([
                dcc.Graph(id=f"scenario-{scenario}-peak-plot")
            ])
        ], className="mb-4"),

        # Timeseries
        dbc.Card([
            dbc.CardHeader([
                dbc.Row([
                    dbc.Col([
                        html.H4("Timeseries", className="mb-0")
                    ], width=2),
                    dbc.Col([
                        html.Label("BREAKDOWN:", style={"fontWeight": "bold", "fontSize": "0.9em"}),
                        dcc.Dropdown(
                            id=f"scenario-{scenario}-timeseries-breakdown",
                            options=[
                                {"label": "Annual Energy Consumption", "value": "None"},
                                {"label": "Annual Energy Consumption by Sector", "value": "Sector"},
                                {"label": "Annual Energy Consumption by End Use", "value": "End Use"}
                            ],
                            value="None",
                            clearable=False
                        )
                    ], width=3),
                    dbc.Col([
                        html.Label("RESAMPLE:", style={"fontWeight": "bold", "fontSize": "0.9em"}),
                        dcc.Dropdown(
                            id=f"scenario-{scenario}-timeseries-resample",
                            options=[{"label": val, "value": val} for val in literal_to_list(ResampleOptions)],
                            value="Daily Mean",
                            clearable=False
                        )
                    ], width=2),
                    dbc.Col([
                        html.Label("WEATHER VAR (Optional):", style={"fontWeight": "bold", "fontSize": "0.9em"}),
                        dcc.Dropdown(
                            id=f"scenario-{scenario}-timeseries-weather",
                            options=[{"label": val, "value": val} for val in literal_to_list(WeatherVar)],
                            value=None,
                            clearable=True,
                            placeholder="Select weather var..."
                        )
                    ], width=3)
                ], align="center")
            ]),
            dbc.CardBody([
                dcc.Graph(id=f"scenario-{scenario}-timeseries-plot"),
                dbc.Row([
                    dbc.Col([
                        html.Label("Select Years:", style={"fontWeight": "bold"}),
                        create_styled_checklist(
                            [str(year) for year in years],
                            f"scenario-{scenario}-timeseries-years",
                            [str(year) for year in years[:2]] if len(years) >= 2 else [str(years[0])] if years else []
                        )
                    ], width=12),
                ], className="mb-3")
            ])
        ], className="mb-4"),

        # Yearly
        dbc.Card([
            dbc.CardHeader([
                dbc.Row([
                    dbc.Col([
                        html.H4("Yearly", className="mb-0")
                    ], width=2),
                    dbc.Col([
                        html.Label("BREAKDOWN:", style={"fontWeight": "bold", "fontSize": "0.9em"}),
                        dcc.Dropdown(
                            id=f"scenario-{scenario}-yearly-breakdown",
                            options=[
                                {"label": "Annual Energy Consumption", "value": "None"},
                                {"label": "Annual Energy Consumption by Sector", "value": "Sector"},
                                {"label": "Annual Energy Consumption by End Use", "value": "End Use"}
                            ],
                            value="None",
                            clearable=False
                        )
                    ], width=3),
                    dbc.Col([
                        html.Label("RESAMPLE:", style={"fontWeight": "bold", "fontSize": "0.9em"}),
                        dcc.Dropdown(
                            id=f"scenario-{scenario}-yearly-resample",
                            options=[{"label": val, "value": val} for val in literal_to_list(ResampleOptions)],
                            value="Daily Mean",
                            clearable=False
                        )
                    ], width=2),
                    dbc.Col([
                        html.Label("YEAR:", style={"fontWeight": "bold", "fontSize": "0.9em"}),
                        dcc.Dropdown(
                            id=f"scenario-{scenario}-yearly-year",
                            options=[{"label": str(year), "value": year} for year in years],
                            value=years[0] if years else None,
                            clearable=False
                        )
                    ], width=2),
                    dbc.Col([
                        html.Label("WEATHER VAR (Optional):", style={"fontWeight": "bold", "fontSize": "0.9em"}),
                        dcc.Dropdown(
                            id=f"scenario-{scenario}-yearly-weather",
                            options=[{"label": val, "value": val} for val in literal_to_list(WeatherVar)],
                            value=None,
                            clearable=True,
                            placeholder="Select weather var..."
                        )
                    ], width=3)
                ], align="center")
            ]),
            dbc.CardBody([
                dcc.Graph(id=f"scenario-{scenario}-yearly-plot")
            ])
        ], className="mb-4"),

        # Seasonal Load Lines
        dbc.Card([
            dbc.CardHeader([
                dbc.Row([
                    dbc.Col([
                        html.H4("Seasonal Load Lines", className="mb-0")
                    ], width=3),
                    dbc.Col([
                        html.Label("TIME GROUP:", style={"fontWeight": "bold", "fontSize": "0.9em"}),
                        dcc.RadioItems(
                            id=f"scenario-{scenario}-seasonal-lines-timegroup",
                            options=[{"label": val, "value": val} for val in literal_to_list(TimeGroup)],
                            value="Seasonal"
                        )
                    ], width=4),
                    dbc.Col([
                        html.Label("AGGREGATION:", style={"fontWeight": "bold", "fontSize": "0.9em"}),
                        dcc.Dropdown(
                            id=f"scenario-{scenario}-seasonal-lines-agg",
                            options=[{"label": val, "value": val} for val in literal_to_list(TimeGroupAgg)],
                            value="Average Day",
                            clearable=False
                        )
                    ], width=2),
                    dbc.Col([
                        html.Label("WEATHER VAR:", style={"fontWeight": "bold", "fontSize": "0.9em"}),
                        dcc.Dropdown(
                            id=f"scenario-{scenario}-seasonal-lines-weather",
                            options=[{"label": val, "value": val} for val in literal_to_list(WeatherVar)],
                            value="Temperature",
                            clearable=False
                        )
                    ], width=3)
                ], align="center")
            ]),
            dbc.CardBody([
                dcc.Graph(id=f"scenario-{scenario}-seasonal-lines-plot")
            ])
        ], className="mb-4"),

        # Seasonal Load Area
        dbc.Card([
            dbc.CardHeader([
                dbc.Row([
                    dbc.Col([
                        html.H4("Seasonal Load Area", className="mb-0")
                    ], width=2),
                    dbc.Col([
                        html.Label("BREAKDOWN:", style={"fontWeight": "bold", "fontSize": "0.9em"}),
                        dcc.Dropdown(
                            id=f"scenario-{scenario}-seasonal-area-breakdown",
                            options=[
                                {"label": "Annual Energy Consumption", "value": "None"},
                                {"label": "Annual Energy Consumption by Sector", "value": "Sector"},
                                {"label": "Annual Energy Consumption by End Use", "value": "End Use"}
                            ],
                            value="Sector",
                            clearable=False
                        )
                    ], width=3),
                    dbc.Col([
                        html.Label("YEAR:", style={"fontWeight": "bold", "fontSize": "0.9em"}),
                        dcc.Dropdown(
                            id=f"scenario-{scenario}-seasonal-area-year",
                            options=[{"label": str(year), "value": year} for year in years],
                            value=years[0] if years else None,
                            clearable=False
                        )
                    ], width=2),
                    dbc.Col([
                        html.Label("TIME GROUP AGG:", style={"fontWeight": "bold", "fontSize": "0.9em"}),
                        dcc.Dropdown(
                            id=f"scenario-{scenario}-seasonal-area-agg",
                            options=[{"label": val, "value": val} for val in literal_to_list(TimeGroupAgg)],
                            value="Average Day",
                            clearable=False
                        )
                    ], width=2),
                    dbc.Col([
                        html.Label("TIME GROUP:", style={"fontWeight": "bold", "fontSize": "0.9em"}),
                        dcc.RadioItems(
                            id=f"scenario-{scenario}-seasonal-area-timegroup",
                            options=[{"label": val, "value": val} for val in literal_to_list(TimeGroup)],
                            value="Seasonal"
                        )
                    ], width=3)
                ], align="center", className="mb-2"),
                dbc.Row([
                    dbc.Col([
                        html.Label("WEATHER VAR:", style={"fontWeight": "bold", "fontSize": "0.9em"}),
                        dcc.Dropdown(
                            id=f"scenario-{scenario}-seasonal-area-weather",
                            options=[{"label": val, "value": val} for val in literal_to_list(WeatherVar)],
                            value="Temperature",
                            clearable=False
                        )
                    ], width=3)
                ], align="center")
            ]),
            dbc.CardBody([
                dcc.Graph(id=f"scenario-{scenario}-seasonal-area-plot")
            ])
        ], className="mb-4"),

        # Load Duration Curve
        dbc.Card([
            dbc.CardHeader(html.H4("Load Duration Curve")),
            dbc.CardBody([
                dbc.Row([
                    dbc.Col([
                        html.Label("Select Years:", style={"fontWeight": "bold"}),
                        create_styled_checklist(
                            [str(year) for year in years],
                            f"scenario-{scenario}-load-duration-years",
                            [str(years[0])] if years else []
                        )
                    ], width=12)
                ], className="mb-3"),
                dcc.Graph(id=f"scenario-{scenario}-load-duration-plot")
            ])
        ], className="mb-4")
    ])  # Close the main html.Div


def register_scenario_callbacks(scenario: str, years: list[int], data_handler: APIClient, plotter: StridePlots):
    """
    Register all callbacks for a scenario tab.

    Parameters
    ----------
    scenario : str
        The scenario name
    years : list[int]
        Available years in the project
    data_handler : APIClient
        API client for data access
    plotter : StridePlots
        Plotting utilities
    """

    # Define all input IDs for this scenario
    scenario_input_ids = [
        f"scenario-{scenario}-summary-year",
        f"scenario-{scenario}-consumption-breakdown", f"scenario-{scenario}-consumption-secondary",
        f"scenario-{scenario}-peak-breakdown", f"scenario-{scenario}-peak-secondary",
        f"scenario-{scenario}-timeseries-breakdown", f"scenario-{scenario}-timeseries-resample",
        f"scenario-{scenario}-timeseries-weather", f"scenario-{scenario}-timeseries-years",
        f"scenario-{scenario}-yearly-breakdown", f"scenario-{scenario}-yearly-resample",
        f"scenario-{scenario}-yearly-weather", f"scenario-{scenario}-yearly-year",
        f"scenario-{scenario}-seasonal-lines-timegroup", f"scenario-{scenario}-seasonal-lines-agg",
        f"scenario-{scenario}-seasonal-lines-weather",
        f"scenario-{scenario}-seasonal-area-breakdown", f"scenario-{scenario}-seasonal-area-year",
        f"scenario-{scenario}-seasonal-area-agg", f"scenario-{scenario}-seasonal-area-timegroup",
        f"scenario-{scenario}-seasonal-area-weather",
        f"scenario-{scenario}-load-duration-years"
    ]

    # Save scenario state
    @callback(
        Output(f"scenario-{scenario}-state-store", "data"),
        [Input(input_id, "value") for input_id in scenario_input_ids],
        prevent_initial_call=True
    )
    def save_scenario_state(*values):
        return dict(zip(scenario_input_ids, values))

    # Cache data for summary statistics
    try:
        # Get all consumption and peak demand data for this scenario
        consumption_df = data_handler.get_annual_electricity_consumption(
            scenarios=[scenario],
            years=years
        )
        peak_demand_df = data_handler.get_annual_peak_demand(
            scenarios=[scenario],
            years=years
        )

        # Convert to dictionaries for fast lookup
        consumption_by_year = consumption_df.set_index('year')['value'].to_dict()
        peak_demand_by_year = peak_demand_df.set_index('year')['value'].to_dict()

    except Exception as e:
        print(f"Error caching summary data for scenario {scenario}: {e}")
        consumption_by_year = {}
        peak_demand_by_year = {}

    # Summary Statistics callback
    @callback(
        [
            Output(f"scenario-{scenario}-total-consumption", "children"),
            Output(f"scenario-{scenario}-percent-growth", "children"),
            Output(f"scenario-{scenario}-peak-demand", "children")
        ],
        Input(f"scenario-{scenario}-summary-year", "value"),
        prevent_initial_call=False
    )
    def update_summary_stats(selected_year):
        if not selected_year:
            return "---", "---", "---"

        try:
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
                        growth = ((total_consumption - previous_consumption) / previous_consumption) * 100
                        percent_growth = f"{growth:.1f}"
                    else:
                        percent_growth = "N/A"
                else:
                    percent_growth = "N/A"

            # Get peak demand for selected year
            peak_demand = peak_demand_by_year.get(selected_year, 0)

            return (
                f"{total_consumption / 1e12:.1f}",
                percent_growth,
                f"{peak_demand / 1e6:,.0f}"
            )

        except Exception as e:
            print(f"Error calculating summary stats for {scenario}, year {selected_year}: {e}")
            return "Error", "Error", "Error"

    # Annual Energy Consumption callback
    @callback(
        Output(f"scenario-{scenario}-consumption-plot", "figure"),
        [
            Input(f"scenario-{scenario}-consumption-breakdown", "value"),
            Input(f"scenario-{scenario}-consumption-secondary", "value")
        ],
        prevent_initial_call=False
    )
    def update_consumption_plot(breakdown, secondary_metric):
        try:
            # Convert "None" to None
            breakdown_value = None if breakdown == "None" else breakdown

            # Get consumption data for this scenario
            df = data_handler.get_annual_electricity_consumption(
                scenarios=[scenario],
                group_by=breakdown_value
            )

            # Create plot
            if breakdown_value:
                if breakdown_value == "End Use":
                    breakdown_value="metric"
                fig = plotter.grouped_stacked_bars(df, stack_col=breakdown_value.lower(), value_col="value", group_col="scenario")
            else:
                fig = plotter.grouped_single_bars(df, "year", use_color_manager=False)

            return fig

        except Exception as e:
            print(f"Error in consumption plot: {e}")
            return {"data": [], "layout": {"title": f"Error: {str(e)}"}}

    # Peak Demand callback
    @callback(
        Output(f"scenario-{scenario}-peak-plot", "figure"),
        [
            Input(f"scenario-{scenario}-peak-breakdown", "value"),
            Input(f"scenario-{scenario}-peak-secondary", "value")
        ],
        prevent_initial_call=False
    )
    def update_peak_plot(breakdown, secondary_metric):
        try:
            # Convert "None" to None
            breakdown_value = None if breakdown == "None" else breakdown

            # Get peak demand data for this scenario
            df = data_handler.get_annual_peak_demand(
                scenarios=[scenario],
                group_by=breakdown_value
            )

            # Create plot
            if breakdown_value:
                if breakdown_value == "End Use":
                    breakdown_value="metric"
                fig = plotter.grouped_stacked_bars(df, stack_col=breakdown_value.lower(), value_col="value", group_col="scenario")
            else:
                fig = plotter.grouped_single_bars(df, "year", use_color_manager=False)

            return fig

        except Exception as e:
            print(f"Error in peak plot: {e}")
            return {"data": [], "layout": {"title": f"Error: {str(e)}"}}

    # Timeseries callback
    @callback(
        Output(f"scenario-{scenario}-timeseries-plot", "figure"),
        [
            Input(f"scenario-{scenario}-timeseries-breakdown", "value"),
            Input(f"scenario-{scenario}-timeseries-resample", "value"),
            Input(f"scenario-{scenario}-timeseries-weather", "value"),
            Input(f"scenario-{scenario}-timeseries-years", "value")
        ],
        prevent_initial_call=False
    )
    def update_timeseries_plot(breakdown, resample, weather_var, selected_years):
        if not selected_years:
            return {"data": [], "layout": {"title": "Select years to view data"}}

        try:
            # Convert "None" to None and years to int
            breakdown_value = None if breakdown == "None" else breakdown

            selected_years_int = [int(year) for year in selected_years]

            # Get timeseries data
            df = data_handler.get_timeseries_comparison(
                scenario=scenario,
                years=selected_years_int,
                group_by=breakdown_value,
                resample=resample
            )

            if breakdown_value == "End Use":
                breakdown_value="metric"
            # Use the new time_series function for better multi-year visualization
            fig = plotter.time_series(
                df,
                group_by=breakdown_value.lower() if breakdown_value else None
            )

            return fig

        except Exception as e:
            print(f"Error in timeseries plot: {e}")
            return {"data": [], "layout": {"title": f"Error: {str(e)}"}}

    # Yearly callback (area chart for single year)
    @callback(
        Output(f"scenario-{scenario}-yearly-plot", "figure"),
        [
            Input(f"scenario-{scenario}-yearly-breakdown", "value"),
            Input(f"scenario-{scenario}-yearly-resample", "value"),
            Input(f"scenario-{scenario}-yearly-weather", "value"),
            Input(f"scenario-{scenario}-yearly-year", "value")
        ],
        prevent_initial_call=False
    )
    def update_yearly_plot(breakdown, resample, weather_var, selected_year):
        if not selected_year:
            return {"data": [], "layout": {"title": "Select a year to view data"}}

        try:
            # Convert "None" to None
            breakdown_value = None if breakdown == "None" else breakdown

            # Get timeseries data for single year
            df = data_handler.get_timeseries_comparison(
                scenario=scenario,
                years=[selected_year],
                group_by=breakdown_value,
                resample=resample
            )

            if breakdown_value == "End Use":
                breakdown_value="metric"

            # Use the time_series function with area chart type
            fig = plotter.time_series(
                df,
                group_by=breakdown_value.lower() if breakdown_value else None,
                chart_type="Area"
            )

            return fig

        except Exception as e:
            print(f"Error in yearly plot: {e}")
            return {"data": [], "layout": {"title": f"Error: {str(e)}"}}

    # Seasonal Load Lines callback
    @callback(
        Output(f"scenario-{scenario}-seasonal-lines-plot", "figure"),
        [
            Input(f"scenario-{scenario}-seasonal-lines-timegroup", "value"),
            Input(f"scenario-{scenario}-seasonal-lines-agg", "value"),
            Input(f"scenario-{scenario}-seasonal-lines-weather", "value")
        ],
        prevent_initial_call=False
    )
    def update_seasonal_lines_plot(timegroup, agg, weather_var):
        try:
            # Get seasonal load lines data
            df = data_handler.get_seasonal_load_lines(
                scenario=scenario,
                years=years,  # Use all available years
                group_by=timegroup,
                agg=agg
            )

            # Use the new seasonal_load_lines plotting method
            fig = plotter.seasonal_load_lines(df)

            return fig

        except Exception as e:
            print(f"Error in seasonal lines plot: {e}")
            return {"data": [], "layout": {"title": f"Error: {str(e)}"}}

    # Seasonal Load Area callback
    @callback(
        Output(f"scenario-{scenario}-seasonal-area-plot", "figure"),
        [
            Input(f"scenario-{scenario}-seasonal-area-breakdown", "value"),
            Input(f"scenario-{scenario}-seasonal-area-year", "value"),
            Input(f"scenario-{scenario}-seasonal-area-agg", "value"),
            Input(f"scenario-{scenario}-seasonal-area-timegroup", "value"),
            Input(f"scenario-{scenario}-seasonal-area-weather", "value")
        ],
        prevent_initial_call=False
    )
    def update_seasonal_area_plot(breakdown, selected_year, agg, timegroup, weather_var):
        if not selected_year:
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
                breakdown=breakdown_value
            )

            # Create area plot using the new seasonal_load_area method
            fig = plotter.seasonal_load_area(df)

            return fig

        except Exception as e:
            print(f"Error in seasonal area plot: {e}")
            return {"data": [], "layout": {"title": f"Error: {str(e)}"}}

    # Load Duration Curve callback
    @callback(
        Output(f"scenario-{scenario}-load-duration-plot", "figure"),
        Input(f"scenario-{scenario}-load-duration-years", "value"),
        prevent_initial_call=False
    )
    def update_load_duration_plot(selected_years):
        if not selected_years:
            return {"data": [], "layout": {"title": "Select years to view data"}}

        try:
            # Convert years to int
            selected_years_int = [int(year) for year in selected_years]

            # Get load duration curve data
            df = data_handler.get_load_duration_curve(
                years=selected_years_int,
                scenarios=[scenario]
            )

            return plotter.demand_curve(df)

        except Exception as e:
            print(f"Error in load duration plot: {e}")
            return {"data": [], "layout": {"title": f"Error: {str(e)}"}}