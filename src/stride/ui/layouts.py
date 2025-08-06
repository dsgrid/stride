from dash import html, dcc, Input, Output, callback, State
import dash_bootstrap_components as dbc
from stride.ui.plotting import StridePlots
from stride.api import APIClient, literal_to_list, Sectors, SecondaryMetric
from stride.ui.color_manager import ColorManager
from stride.ui.scenario_layout import create_scenario_layout, register_scenario_callbacks
import json

def create_layout(data_handler: APIClient, plotter: StridePlots, color_manager: ColorManager):
    scenarios = data_handler.scenarios
    sectors = literal_to_list(Sectors)
    years = data_handler.years

    # Create tabs - Home + one for each scenario
    tabs = [
        dbc.Tab(label="Home", tab_id="home")
    ]

    for scenario in scenarios:
        tabs.append(dbc.Tab(label=scenario, tab_id=f"scenario-{scenario}"))

    layout = html.Div([
        html.H1("STRIDE",
                style={"padding": "20px"},
                className="stride-title"),

        # State storage for all input values
        dcc.Store(id="home-state-store", data={}),
        *[dcc.Store(id=f"scenario-{scenario}-state-store", data={}) for scenario in scenarios],

        dbc.Tabs(
            id="main-tabs",
            active_tab="home",
            children=tabs,
            className="custom-tabs"
        ),

        html.Div(id="tab-content")
    ])

    register_callbacks(data_handler, plotter, scenarios, sectors, years, color_manager)

    # Register scenario-specific callbacks for each scenario
    for scenario in scenarios:
        register_scenario_callbacks(scenario, years, data_handler, plotter)

    return layout

def create_home_tab(scenarios: list[str], sectors: list[str], years: list[int], color_manager: ColorManager, stored_state: dict = None):
    """Home tab for comparing scenarios"""

    # Get stored values or use defaults
    stored_state = stored_state or {}

    # Generate scenario CSS from ColorManager
    scenario_css = color_manager.generate_scenario_css()

    def create_styled_checklist(scenarios_list, checklist_id):
        # Get stored value or default
        stored_value = stored_state.get(checklist_id, scenarios_list[:2] if len(scenarios_list) >= 2 else scenarios_list)

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
                options=[{"label": s, "value": s} for s in scenarios_list],
                value=stored_value,
                inline=True,
                className="scenario-checklist"
            )
        ])

    return html.Div([
        # Scenario Comparison Chart
        dbc.Card([
            dbc.CardHeader([
                dbc.Row([
                    dbc.Col([
                        html.H4("Annual Energy Consumption", className="mb-0")
                    ], width=3),
                    dbc.Col([
                        html.Label("LEFT AXIS:", style={"fontWeight": "bold", "fontSize": "0.9em"}),
                        dcc.Dropdown(
                            id="home-consumption-breakdown",
                            options=[
                                {"label": "Annual Energy Consumption", "value": "None"},
                                {"label": "Annual Energy Consumption by Sector", "value": "Sector"},
                                {"label": "Annual Energy Consumption by End Use", "value": "End Use"}
                            ],
                            value=stored_state.get("home-consumption-breakdown", "None"),
                            clearable=False
                        )
                    ], width=4),
                    dbc.Col([
                        html.Label("RIGHT AXIS (Optional):", style={"fontWeight": "bold", "fontSize": "0.9em"}),
                        dcc.Dropdown(
                            id="home-secondary-metric",
                            options=[{"label":val, "value":val} for val in literal_to_list(SecondaryMetric)],
                            value=stored_state.get("home-secondary-metric", None),
                            clearable=True,
                            placeholder="Select secondary metric..."
                        )
                    ], width=5)
                ], align="center")
            ]),
            dbc.CardBody([
                dcc.Graph(id="home-scenario-comparison"),

                dbc.Row([
                    dbc.Col([
                        html.Label("Select Scenarios:", style={"fontWeight": "bold"}),
                        create_styled_checklist(scenarios, "home-scenarios-checklist")
                    ], width=12),
                ], className="mb-3")
            ])
        ], className="mb-4"),

        # Peak Energy Demand Chart
        dbc.Card([
            dbc.CardHeader([
                dbc.Row([
                    dbc.Col([
                        html.H4("Peak Energy Demand", className="mb-0")
                    ], width=3),
                    dbc.Col([
                        html.Label("LEFT AXIS:", style={"fontWeight": "bold", "fontSize": "0.9em"}),
                        dcc.Dropdown(
                            id="home-peak-breakdown",
                            options=[
                                {"label": "Annual Peak Demand", "value": "None"},
                                {"label": "Annual Peak Demand by Sector", "value": "Sector"},
                                {"label": "Annual Peak Demand by End Use", "value": "End Use"}
                            ],
                            value=stored_state.get("home-peak-breakdown", "None"),
                            clearable=False
                        )
                    ], width=4),
                    dbc.Col([
                        html.Label("RIGHT AXIS (Optional):", style={"fontWeight": "bold", "fontSize": "0.9em"}),
                        dcc.Dropdown(
                            id="home-peak-secondary-metric",
                            options=[{"label":val, "value":val} for val in literal_to_list(SecondaryMetric)],
                            value=stored_state.get("home-peak-secondary-metric", None),
                            clearable=True,
                            placeholder="Select secondary metric..."
                        )
                    ], width=5)
                ], align="center")
            ]),
            dbc.CardBody([
                dcc.Graph(id="home-sector-breakdown"),

                dbc.Row([
                    dbc.Col([
                        html.Label("Select Scenarios:", style={"fontWeight": "bold"}),
                        create_styled_checklist(scenarios, "home-scenarios-2-checklist")
                    ], width=12),
                ], className="mb-3")
            ])
        ], className="mb-4"),

        # Load Duration Curve
        dbc.Card([
            dbc.CardHeader(html.H4("Load Duration Curve")),
            dbc.CardBody([
                dbc.Row([
                    dbc.Col([
                        html.Label("Select Year:", style={"fontWeight": "bold"}),
                        dcc.Dropdown(
                            id="home-year-dropdown",
                            options=[{"label": str(year), "value": year} for year in years],
                            value=stored_state.get("home-year-dropdown", years[0] if years else None),
                            clearable=False
                        )
                    ], width=3),
                    dbc.Col([
                        html.Label("Select Scenarios:", style={"fontWeight": "bold"}),
                        create_styled_checklist(scenarios, "home-scenarios-3-checklist")
                    ], width=9)
                ], className="mb-3"),
                dcc.Graph(id="home-load-duration")
            ])
        ], className="mb-4"),

        # Scenario Time Series Comparison
        dbc.Card([
            dbc.CardHeader([
                dbc.Row([
                    dbc.Col([
                        html.H4("Scenario Time Series Comparison", className="mb-0")
                    ], width=3),
                    dbc.Col([
                        html.Label("CHART TYPE:", style={"fontWeight": "bold", "fontSize": "0.9em"}),
                        dcc.Dropdown(
                            id="home-timeseries-chart-type",
                            options=[
                                {"label": "Line", "value": "Line"},
                                {"label": "Area", "value": "Area"}
                            ],
                            value=stored_state.get("home-timeseries-chart-type", "Line"),
                            clearable=False
                        )
                    ], width=2),
                    dbc.Col([
                        html.Label("BREAKDOWN:", style={"fontWeight": "bold", "fontSize": "0.9em"}),
                        dcc.Dropdown(
                            id="home-timeseries-breakdown",
                            options=[
                                {"label": "Annual Energy Consumption", "value": "None"},
                                {"label": "Annual Energy Consumption by Sector", "value": "Sector"},
                                {"label": "Annual Energy Consumption by End Use", "value": "End Use"}
                            ],
                            value=stored_state.get("home-timeseries-breakdown", "None"),
                            clearable=False
                        )
                    ], width=4),
                    dbc.Col([
                        html.Label("RIGHT AXIS (Optional):", style={"fontWeight": "bold", "fontSize": "0.9em"}),
                        dcc.Dropdown(
                            id="home-timeseries-secondary-metric",
                            options=[{"label":val, "value":val} for val in literal_to_list(SecondaryMetric)],
                            value=stored_state.get("home-timeseries-secondary-metric", None),
                            clearable=True,
                            placeholder="Select secondary metric..."
                        )
                    ], width=3)
                ], align="center")
            ]),
            dbc.CardBody([
                dcc.Graph(id="home-scenario-timeseries"),
                dbc.Row([
                    dbc.Col([
                        html.Label("Select Scenarios:", style={"fontWeight": "bold"}),
                        create_styled_checklist(scenarios, "home-scenarios-4-checklist")
                    ], width=12),
                ], className="mb-3")
            ])
        ])
    ])

def create_scenario_tab(scenario: str, sectors: list[str], years: list[int]):
    """Individual scenario tab for detailed analysis - DEPRECATED: Use create_scenario_layout instead"""
    # This function is now replaced by create_scenario_layout in scenario_layout.py
    # Keeping for backwards compatibility but it's not used anymore
    return html.Div([
        html.H3(f"Detailed Analysis: {scenario}", className="mb-4"),
        html.P("This tab has been replaced with the enhanced scenario layout.", className="text-muted")
    ])

def register_callbacks(data_handler: APIClient, plotter: StridePlots, scenarios: list[str], sectors: list[str], years: list[int], color_manager: ColorManager):

    # State management callbacks
    home_input_ids = [
        "home-consumption-breakdown", "home-secondary-metric", "home-scenarios-checklist",
        "home-peak-breakdown", "home-peak-secondary-metric", "home-scenarios-2-checklist",
        "home-year-dropdown", "home-scenarios-3-checklist",
        "home-timeseries-chart-type", "home-timeseries-breakdown",
        "home-timeseries-secondary-metric", "home-scenarios-4-checklist"
    ]

    # Save home tab state
    @callback(
        Output("home-state-store", "data"),
        [Input(input_id, "value") for input_id in home_input_ids],
        prevent_initial_call=True
    )
    def save_home_state(*values):
        return dict(zip(home_input_ids, values))

    # Tab content callback with state restoration
    @callback(
        Output("tab-content", "children"),
        Input("main-tabs", "active_tab"),
        State("home-state-store", "data"),
        *[State(f"scenario-{scenario}-state-store", "data") for scenario in scenarios]
    )
    def update_tab_content(active_tab, home_state, *scenario_states):
        if active_tab == "home":
            return create_home_tab(scenarios, sectors, years, color_manager, home_state)
        elif active_tab.startswith("scenario-"):
            scenario_name = active_tab.replace("scenario-", "")
            scenario_index = scenarios.index(scenario_name) if scenario_name in scenarios else 0
            scenario_state = scenario_states[scenario_index] if scenario_index < len(scenario_states) else {}
            return create_scenario_layout(scenario_name, years, data_handler, color_manager, scenario_state)
        return html.Div("Select a tab")

    # Home tab callbacks
    @callback(
        Output("home-scenario-comparison", "figure"),
        Input("home-scenarios-checklist", "value"),
        Input("home-consumption-breakdown", "value"),
        Input("home-secondary-metric", "value"),
        prevent_initial_call=False,
    )
    def update_home_scenario_comparison(selected_scenarios, breakdown, secondary_metric):
        print(f"Callback triggered with scenarios: {selected_scenarios}, breakdown: {breakdown}")

        if not selected_scenarios:
            return {"data": [], "layout": {"title": "Select scenarios to view data"}}

        try:
            # Convert "None" to None
            breakdown_value = None if breakdown == "None" else breakdown

            # Get the main consumption data
            df = data_handler.get_annual_electricity_consumption(
                scenarios=selected_scenarios,
                group_by=breakdown_value
            )

            print(f"Retrieved data with shape: {df.shape}")

            # Create the main plot
            if breakdown_value:
                if breakdown_value == "End Use":
                    breakdown_value="metric"
                fig = plotter.grouped_stacked_bars(df, stack_col=breakdown_value.lower(), value_col="value")
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

    @callback(
        Output("home-sector-breakdown", "figure"),
        Input("home-scenarios-2-checklist", "value"),
        Input("home-peak-breakdown", "value"),
        Input("home-peak-secondary-metric", "value"),
        prevent_initial_call=False,
    )
    def update_home_sector_breakdown(selected_scenarios, breakdown, secondary_metric):
        print(f"Peak demand callback triggered with scenarios: {selected_scenarios}, breakdown: {breakdown}")

        if not selected_scenarios:
            return {"data": [], "layout": {"title": "Select scenarios to view data"}}

        try:
            # Convert "None" to None
            breakdown_value = None if breakdown == "None" else breakdown

            # Get the peak demand data
            df = data_handler.get_annual_peak_demand(
                scenarios=selected_scenarios,
                group_by=breakdown_value
            )

            print(f"Retrieved peak demand data with shape: {df.shape}")

            # Create the main plot
            if breakdown_value:
                if breakdown_value == "End Use":
                    breakdown_value="metric"
                fig = plotter.grouped_stacked_bars(df, stack_col=breakdown_value.lower(), value_col="value")
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

    @callback(
        Output("home-load-duration", "figure"),
        Input("home-scenarios-3-checklist", "value"),
        Input("home-year-dropdown", "value")
    )
    def update_home_load_duration(selected_scenarios, selected_year):
        if not selected_scenarios or not selected_year:
            return {}

        df = data_handler.get_load_duration_curve(
            years=selected_year,
            scenarios=selected_scenarios
        )
        return plotter.demand_curve(df)

    @callback(
        Output("home-scenario-timeseries", "figure"),
        Input("home-scenarios-4-checklist", "value"),
        Input("home-timeseries-chart-type", "value"),
        Input("home-timeseries-breakdown", "value"),
        Input("home-timeseries-secondary-metric", "value"),
        prevent_initial_call=False,
    )
    def update_home_scenario_timeseries(selected_scenarios, chart_type, breakdown, secondary_metric):
        print(f"Timeseries callback triggered with scenarios: {selected_scenarios}, chart_type: {chart_type}, breakdown: {breakdown}")

        if not selected_scenarios:
            return {"data": [], "layout": {"title": "Select scenarios to view data"}}

        try:
            # Convert "None" to None
            breakdown_value = None if breakdown == "None" else breakdown

            # Get the consumption data for all scenarios
            df = data_handler.get_annual_electricity_consumption(
                scenarios=selected_scenarios,
                group_by=breakdown_value
            )

            print(f"Retrieved timeseries data with shape: {df.shape}")

            if breakdown_value == "End Use":
                breakdown_value="metric"
            # Create the faceted plot
            fig = plotter.faceted_time_series(
                df,
                chart_type=chart_type,
                group_by=breakdown_value.lower() if breakdown_value else None,
                value_col="value"
            )

            return fig

        except Exception as e:
            print(f"Error in update_home_scenario_timeseries: {e}")
            import traceback
            traceback.print_exc()
            return {"data": [], "layout": {"title": f"Error: {str(e)}"}}