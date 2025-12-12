from typing import Any

import dash_bootstrap_components as dbc  # type: ignore
from dash import dcc, html

from stride.api.utils import SecondaryMetric, literal_to_list
from stride.ui.color_manager import ColorManager


def create_home_layout(
    scenarios: list[str],
    years: list[int],
    color_manager: ColorManager,
    stored_state: dict[str, Any] | None = None,
) -> html.Div:
    """Home tab for comparing scenarios"""

    # Get stored values or use defaults
    stored_state = stored_state or {}

    # Generate scenario CSS from ColorManager
    scenario_css = color_manager.generate_scenario_css()

    def create_styled_checklist(scenarios_list: list[str], checklist_id: Any) -> html.Div:
        # Get stored value or default
        stored_value = stored_state.get(
            checklist_id, scenarios_list[:2] if len(scenarios_list) >= 2 else scenarios_list
        )

        # Create custom styled buttons for each scenario
        scenario_buttons = []
        for scenario in scenarios_list:
            # Get the scenario color from color manager
            base_color = color_manager.get_color(scenario)
            r, g, b, _ = color_manager._str_to_rgba(base_color)

            # Determine if scenario is selected
            is_selected = scenario in stored_value

            # Set alpha based on selection state
            alpha = 0.9 if is_selected else 0.3
            bg_color = f"rgba({r}, {g}, {b}, {alpha})"
            border_color = f"rgba({r}, {g}, {b}, 1.0)"

            scenario_buttons.append(
                html.Button(
                    scenario,
                    id={"type": checklist_id, "index": scenario},
                    n_clicks=0,
                    style={
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
                    },
                    className="scenario-button",
                )
            )

        return html.Div(
            [
                html.Div(
                    scenario_buttons,
                    style={"display": "flex", "flexWrap": "wrap", "gap": "4px"},
                ),
                # Hidden store to track selected scenarios
                dcc.Store(id=checklist_id, data=stored_value),
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
                    dbc.CardHeader(
                        [
                            dbc.Row(
                                [
                                    dbc.Col(
                                        [html.H4("Load Duration Curve", className="mb-0")],
                                        width=3,
                                    ),
                                    dbc.Col(
                                        [
                                            html.Label(
                                                "SELECT YEAR:",
                                                style={"fontWeight": "bold", "fontSize": "0.9em"},
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
                                        width=9,
                                    ),
                                ],
                                align="center",
                            )
                        ]
                    ),
                    dbc.CardBody(
                        [
                            dcc.Graph(id="home-load-duration"),
                            dbc.Row(
                                [
                                    dbc.Col(
                                        [
                                            create_styled_checklist(
                                                scenarios, "home-scenarios-3-checklist"
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
