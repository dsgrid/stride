from dash import html, dcc
import dash_bootstrap_components as dbc
from stride.api import literal_to_list, SecondaryMetric
from stride.ui.color_manager import ColorManager


def create_home_layout(
    scenarios: list[str], years: list[int], color_manager: ColorManager, stored_state: dict = None
):
    """Home tab for comparing scenarios"""

    # Get stored values or use defaults
    stored_state = stored_state or {}

    # Generate scenario CSS from ColorManager
    scenario_css = color_manager.generate_scenario_css()

    def create_styled_checklist(scenarios_list, checklist_id):
        # Get stored value or default
        stored_value = stored_state.get(
            checklist_id, scenarios_list[:2] if len(scenarios_list) >= 2 else scenarios_list
        )

        return html.Div(
            [
                # Add scenario-specific CSS styles
                html.Div(
                    [
                        html.Script(
                            f"""
                var style = document.createElement('style');
                style.textContent = `{scenario_css}`;
                document.head.appendChild(style);
                """
                        )
                    ]
                ),
                dbc.Checklist(
                    id=checklist_id,
                    options=[{"label": s, "value": s} for s in scenarios_list],
                    value=stored_value,
                    inline=True,
                    className="scenario-checklist",
                ),
            ]
        )

    return html.Div(
        [
            # Scenario Comparison Chart
            dbc.Card(
                [
                    dbc.CardHeader(
                        [
                            dbc.Row(
                                [
                                    dbc.Col(
                                        [html.H4("Annual Energy Consumption", className="mb-0")],
                                        width=3,
                                    ),
                                    dbc.Col(
                                        [
                                            html.Label(
                                                "LEFT AXIS:",
                                                style={"fontWeight": "bold", "fontSize": "0.9em"},
                                            ),
                                            dcc.Dropdown(
                                                id="home-consumption-breakdown",
                                                options=[
                                                    {
                                                        "label": "Annual Energy Consumption",
                                                        "value": "None",
                                                    },
                                                    {
                                                        "label": "Annual Energy Consumption by Sector",
                                                        "value": "Sector",
                                                    },
                                                    {
                                                        "label": "Annual Energy Consumption by End Use",
                                                        "value": "End Use",
                                                    },
                                                ],
                                                value=stored_state.get(
                                                    "home-consumption-breakdown", "None"
                                                ),
                                                clearable=False,
                                            ),
                                        ],
                                        width=4,
                                    ),
                                    dbc.Col(
                                        [
                                            html.Label(
                                                "RIGHT AXIS (Optional):",
                                                style={"fontWeight": "bold", "fontSize": "0.9em"},
                                            ),
                                            dcc.Dropdown(
                                                id="home-secondary-metric",
                                                options=[
                                                    {"label": val, "value": val}
                                                    for val in literal_to_list(SecondaryMetric)
                                                ],
                                                value=stored_state.get(
                                                    "home-secondary-metric", None
                                                ),
                                                clearable=True,
                                                placeholder="Select secondary metric...",
                                            ),
                                        ],
                                        width=5,
                                    ),
                                ],
                                align="center",
                            )
                        ]
                    ),
                    dbc.CardBody(
                        [
                            dcc.Graph(id="home-scenario-comparison"),
                            dbc.Row(
                                [
                                    dbc.Col(
                                        [
                                            html.Label(
                                                "Select Scenarios:", style={"fontWeight": "bold"}
                                            ),
                                            create_styled_checklist(
                                                scenarios, "home-scenarios-checklist"
                                            ),
                                        ],
                                        width=12,
                                    ),
                                ],
                                className="mb-3",
                            ),
                        ]
                    ),
                ],
                className="mb-4",
            ),
            # Peak Energy Demand Chart
            dbc.Card(
                [
                    dbc.CardHeader(
                        [
                            dbc.Row(
                                [
                                    dbc.Col(
                                        [html.H4("Peak Energy Demand", className="mb-0")], width=3
                                    ),
                                    dbc.Col(
                                        [
                                            html.Label(
                                                "LEFT AXIS:",
                                                style={"fontWeight": "bold", "fontSize": "0.9em"},
                                            ),
                                            dcc.Dropdown(
                                                id="home-peak-breakdown",
                                                options=[
                                                    {
                                                        "label": "Annual Peak Demand",
                                                        "value": "None",
                                                    },
                                                    {
                                                        "label": "Annual Peak Demand by Sector",
                                                        "value": "Sector",
                                                    },
                                                    {
                                                        "label": "Annual Peak Demand by End Use",
                                                        "value": "End Use",
                                                    },
                                                ],
                                                value=stored_state.get(
                                                    "home-peak-breakdown", "None"
                                                ),
                                                clearable=False,
                                            ),
                                        ],
                                        width=4,
                                    ),
                                    dbc.Col(
                                        [
                                            html.Label(
                                                "RIGHT AXIS (Optional):",
                                                style={"fontWeight": "bold", "fontSize": "0.9em"},
                                            ),
                                            dcc.Dropdown(
                                                id="home-peak-secondary-metric",
                                                options=[
                                                    {"label": val, "value": val}
                                                    for val in literal_to_list(SecondaryMetric)
                                                ],
                                                value=stored_state.get(
                                                    "home-peak-secondary-metric", None
                                                ),
                                                clearable=True,
                                                placeholder="Select secondary metric...",
                                            ),
                                        ],
                                        width=5,
                                    ),
                                ],
                                align="center",
                            )
                        ]
                    ),
                    dbc.CardBody(
                        [
                            dcc.Graph(id="home-sector-breakdown"),
                            dbc.Row(
                                [
                                    dbc.Col(
                                        [
                                            html.Label(
                                                "Select Scenarios:", style={"fontWeight": "bold"}
                                            ),
                                            create_styled_checklist(
                                                scenarios, "home-scenarios-2-checklist"
                                            ),
                                        ],
                                        width=12,
                                    ),
                                ],
                                className="mb-3",
                            ),
                        ]
                    ),
                ],
                className="mb-4",
            ),
            # Load Duration Curve
            dbc.Card(
                [
                    dbc.CardHeader(html.H4("Load Duration Curve")),
                    dbc.CardBody(
                        [
                            dbc.Row(
                                [
                                    dbc.Col(
                                        [
                                            html.Label(
                                                "Select Year:", style={"fontWeight": "bold"}
                                            ),
                                            dcc.Dropdown(
                                                id="home-year-dropdown",
                                                options=[
                                                    {"label": str(year), "value": year}
                                                    for year in years
                                                ],
                                                value=stored_state.get(
                                                    "home-year-dropdown",
                                                    years[0] if years else None,
                                                ),
                                                clearable=False,
                                            ),
                                        ],
                                        width=3,
                                    ),
                                    dbc.Col(
                                        [
                                            html.Label(
                                                "Select Scenarios:", style={"fontWeight": "bold"}
                                            ),
                                            create_styled_checklist(
                                                scenarios, "home-scenarios-3-checklist"
                                            ),
                                        ],
                                        width=9,
                                    ),
                                ],
                                className="mb-3",
                            ),
                            dcc.Graph(id="home-load-duration"),
                        ]
                    ),
                ],
                className="mb-4",
            ),
            # Scenario Time Series Comparison
            dbc.Card(
                [
                    dbc.CardHeader(
                        [
                            dbc.Row(
                                [
                                    dbc.Col(
                                        [
                                            html.H4(
                                                "Scenario Time Series Comparison", className="mb-0"
                                            )
                                        ],
                                        width=3,
                                    ),
                                    dbc.Col(
                                        [
                                            html.Label(
                                                "CHART TYPE:",
                                                style={"fontWeight": "bold", "fontSize": "0.9em"},
                                            ),
                                            dcc.Dropdown(
                                                id="home-timeseries-chart-type",
                                                options=[
                                                    {"label": "Line", "value": "Line"},
                                                    {"label": "Area", "value": "Area"},
                                                ],
                                                value=stored_state.get(
                                                    "home-timeseries-chart-type", "Line"
                                                ),
                                                clearable=False,
                                            ),
                                        ],
                                        width=2,
                                    ),
                                    dbc.Col(
                                        [
                                            html.Label(
                                                "BREAKDOWN:",
                                                style={"fontWeight": "bold", "fontSize": "0.9em"},
                                            ),
                                            dcc.Dropdown(
                                                id="home-timeseries-breakdown",
                                                options=[
                                                    {
                                                        "label": "Annual Energy Consumption",
                                                        "value": "None",
                                                    },
                                                    {
                                                        "label": "Annual Energy Consumption by Sector",
                                                        "value": "Sector",
                                                    },
                                                    {
                                                        "label": "Annual Energy Consumption by End Use",
                                                        "value": "End Use",
                                                    },
                                                ],
                                                value=stored_state.get(
                                                    "home-timeseries-breakdown", "None"
                                                ),
                                                clearable=False,
                                            ),
                                        ],
                                        width=4,
                                    ),
                                    dbc.Col(
                                        [
                                            html.Label(
                                                "RIGHT AXIS (Optional):",
                                                style={"fontWeight": "bold", "fontSize": "0.9em"},
                                            ),
                                            dcc.Dropdown(
                                                id="home-timeseries-secondary-metric",
                                                options=[
                                                    {"label": val, "value": val}
                                                    for val in literal_to_list(SecondaryMetric)
                                                ],
                                                value=stored_state.get(
                                                    "home-timeseries-secondary-metric", None
                                                ),
                                                clearable=True,
                                                placeholder="Select secondary metric...",
                                            ),
                                        ],
                                        width=3,
                                    ),
                                ],
                                align="center",
                            )
                        ]
                    ),
                    dbc.CardBody(
                        [
                            dcc.Graph(id="home-scenario-timeseries"),
                            dbc.Row(
                                [
                                    dbc.Col(
                                        [
                                            html.Label(
                                                "Select Scenarios:", style={"fontWeight": "bold"}
                                            ),
                                            create_styled_checklist(
                                                scenarios, "home-scenarios-4-checklist"
                                            ),
                                        ],
                                        width=12,
                                    ),
                                ],
                                className="mb-3",
                            ),
                        ]
                    ),
                ]
            ),
        ]
    )
