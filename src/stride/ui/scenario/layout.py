from typing import Any
from dash import html, dcc
import dash_bootstrap_components as dbc  # type: ignore
from stride.api.utils import (
    literal_to_list,
    SecondaryMetric,
    ResampleOptions,
    WeatherVar,
    TimeGroup,
    TimeGroupAgg,
)
from stride.ui.color_manager import ColorManager


def create_scenario_layout(
    years: list[int], color_manager: ColorManager, stored_state: dict[Any, Any] | None = None
) -> html.Div:
    """
    Create the layout for the individual scenario view based on scenario_tab_design.md.

    Parameters
    ----------
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

    def create_styled_checklist(
        items_list: list[Any], checklist_id: str, default_selection: list[Any] | None = None
    ) -> html.Div:
        """
        Create a styled checklist similar to home tab.

        Parameters
        ----------
        items_list : list
            List of items to display in the checklist
        checklist_id : str
            Unique identifier for the checklist component
        default_selection : list, optional
            Default selected items, by default None

        Returns
        -------
        html.Div
            Dash HTML div containing the styled checklist
        """
        # Get stored value or use default
        stored_value = stored_state.get(
            checklist_id, default_selection if default_selection else items_list
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
                    options=[{"label": item, "value": item} for item in items_list],
                    value=stored_value,
                    inline=True,
                    className="scenario-checklist",
                ),
            ]
        )

    # Create summary stat card helper
    def create_summary_stat_card(stat_id: str, title: str) -> dbc.Card:
        """
        Create a summary statistic card.

        Parameters
        ----------
        stat_id : str
            Unique identifier for the statistic value element
        title : str
            Display title for the statistic

        Returns
        -------
        dbc.Card
            Dash Bootstrap Card component with formatted statistic display
        """
        return dbc.Card(
            [
                dbc.CardBody(
                    [
                        html.H2(
                            id=stat_id,
                            className="text-center mb-2",
                            style={"color": "#007bff", "fontWeight": "bold"},
                        ),
                        html.P(
                            title,
                            className="text-center mb-0",
                            style={"fontSize": "0.9rem", "fontWeight": "500"},
                        ),
                    ],
                    className="py-3",
                )
            ],
            className="h-100",
        )

    return html.Div(
        [
            # Header
            html.H2(id="scenario-title", className="mb-4 scenario-title"),
            # Summary Stats Section
            dbc.Card(
                [
                    dbc.CardHeader(
                        [
                            dbc.Row(
                                [
                                    dbc.Col([html.H4("Summary Stats", className="mb-0")], width=3),
                                    dbc.Col(
                                        [
                                            html.Label(
                                                "Year:",
                                                style={"fontWeight": "bold", "fontSize": "0.9em"},
                                            ),
                                            dcc.Dropdown(
                                                id="scenario-summary-year",
                                                options=[
                                                    {"label": str(year), "value": year}
                                                    for year in years
                                                ],
                                                value=stored_state.get(
                                                    "scenario-summary-year",
                                                    years[-1] if years else None,
                                                ),
                                                clearable=False,
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
                            dbc.Row(
                                [
                                    dbc.Col(
                                        [
                                            create_summary_stat_card(
                                                "scenario-total-consumption",
                                                "Total Consumption (MWh)",
                                            )
                                        ],
                                        width=4,
                                    ),
                                    dbc.Col(
                                        [
                                            create_summary_stat_card(
                                                "scenario-percent-growth", "Percent Growth (%)"
                                            )
                                        ],
                                        width=4,
                                    ),
                                    dbc.Col(
                                        [
                                            create_summary_stat_card(
                                                "scenario-peak-demand", "Peak Demand (MW)"
                                            )
                                        ],
                                        width=4,
                                    ),
                                ]
                            )
                        ]
                    ),
                ],
                className="mb-4",
            ),
            # Annual Energy Consumption
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
                                                id="scenario-consumption-breakdown",
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
                                                    "scenario-consumption-breakdown", "None"
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
                                                id="scenario-consumption-secondary",
                                                options=[
                                                    {"label": val, "value": val}
                                                    for val in literal_to_list(SecondaryMetric)
                                                ],
                                                value=stored_state.get(
                                                    "scenario-consumption-secondary", None
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
                    dbc.CardBody([dcc.Graph(id="scenario-consumption-plot")]),
                ],
                className="mb-4",
            ),
            # Peak Demand
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
                                                id="scenario-peak-breakdown",
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
                                                value="None",
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
                                                id="scenario-peak-secondary",
                                                options=[
                                                    {"label": val, "value": val}
                                                    for val in literal_to_list(SecondaryMetric)
                                                ],
                                                value=None,
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
                    dbc.CardBody([dcc.Graph(id="scenario-peak-plot")]),
                ],
                className="mb-4",
            ),
            # Timeseries
            dbc.Card(
                [
                    dbc.CardHeader(
                        [
                            dbc.Row(
                                [
                                    dbc.Col([html.H4("Timeseries", className="mb-0")], width=2),
                                    dbc.Col(
                                        [
                                            html.Label(
                                                "BREAKDOWN:",
                                                style={"fontWeight": "bold", "fontSize": "0.9em"},
                                            ),
                                            dcc.Dropdown(
                                                id="scenario-timeseries-breakdown",
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
                                                value="None",
                                                clearable=False,
                                            ),
                                        ],
                                        width=3,
                                    ),
                                    dbc.Col(
                                        [
                                            html.Label(
                                                "RESAMPLE:",
                                                style={"fontWeight": "bold", "fontSize": "0.9em"},
                                            ),
                                            dcc.Dropdown(
                                                id="scenario-timeseries-resample",
                                                options=[
                                                    {"label": val, "value": val}
                                                    for val in literal_to_list(ResampleOptions)
                                                ],
                                                value="Daily Mean",
                                                clearable=False,
                                            ),
                                        ],
                                        width=2,
                                    ),
                                    dbc.Col(
                                        [
                                            html.Label(
                                                "WEATHER VAR (Optional):",
                                                style={"fontWeight": "bold", "fontSize": "0.9em"},
                                            ),
                                            dcc.Dropdown(
                                                id="scenario-timeseries-weather",
                                                options=[
                                                    {"label": val, "value": val}
                                                    for val in literal_to_list(WeatherVar)
                                                ],
                                                value=None,
                                                clearable=True,
                                                placeholder="Select weather var...",
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
                            dcc.Graph(id="scenario-timeseries-plot"),
                            dbc.Row(
                                [
                                    dbc.Col(
                                        [
                                            html.Label(
                                                "Select Years:", style={"fontWeight": "bold"}
                                            ),
                                            create_styled_checklist(
                                                [str(year) for year in years],
                                                "scenario-timeseries-years",
                                                [str(year) for year in years[:2]]
                                                if len(years) >= 2
                                                else [str(years[0])]
                                                if years
                                                else [],
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
            # Yearly
            dbc.Card(
                [
                    dbc.CardHeader(
                        [
                            dbc.Row(
                                [
                                    dbc.Col([html.H4("Yearly", className="mb-0")], width=2),
                                    dbc.Col(
                                        [
                                            html.Label(
                                                "BREAKDOWN:",
                                                style={"fontWeight": "bold", "fontSize": "0.9em"},
                                            ),
                                            dcc.Dropdown(
                                                id="scenario-yearly-breakdown",
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
                                                value="None",
                                                clearable=False,
                                            ),
                                        ],
                                        width=3,
                                    ),
                                    dbc.Col(
                                        [
                                            html.Label(
                                                "RESAMPLE:",
                                                style={"fontWeight": "bold", "fontSize": "0.9em"},
                                            ),
                                            dcc.Dropdown(
                                                id="scenario-yearly-resample",
                                                options=[
                                                    {"label": val, "value": val}
                                                    for val in literal_to_list(ResampleOptions)
                                                ],
                                                value="Daily Mean",
                                                clearable=False,
                                            ),
                                        ],
                                        width=2,
                                    ),
                                    dbc.Col(
                                        [
                                            html.Label(
                                                "YEAR:",
                                                style={"fontWeight": "bold", "fontSize": "0.9em"},
                                            ),
                                            dcc.Dropdown(
                                                id="scenario-yearly-year",
                                                options=[
                                                    {"label": str(year), "value": year}
                                                    for year in years
                                                ],
                                                value=years[0] if years else None,
                                                clearable=False,
                                            ),
                                        ],
                                        width=2,
                                    ),
                                    dbc.Col(
                                        [
                                            html.Label(
                                                "WEATHER VAR (Optional):",
                                                style={"fontWeight": "bold", "fontSize": "0.9em"},
                                            ),
                                            dcc.Dropdown(
                                                id="scenario-yearly-weather",
                                                options=[
                                                    {"label": val, "value": val}
                                                    for val in literal_to_list(WeatherVar)
                                                ],
                                                value=None,
                                                clearable=True,
                                                placeholder="Select weather var...",
                                            ),
                                        ],
                                        width=3,
                                    ),
                                ],
                                align="center",
                            )
                        ]
                    ),
                    dbc.CardBody([dcc.Graph(id="scenario-yearly-plot")]),
                ],
                className="mb-4",
            ),
            # Seasonal Load Lines
            dbc.Card(
                [
                    dbc.CardHeader(
                        [
                            dbc.Row(
                                [
                                    dbc.Col(
                                        [html.H4("Seasonal Load Lines", className="mb-0")], width=3
                                    ),
                                    dbc.Col(
                                        [
                                            html.Label(
                                                "TIME GROUP:",
                                                style={"fontWeight": "bold", "fontSize": "0.9em"},
                                            ),
                                            dcc.RadioItems(
                                                id="scenario-seasonal-lines-timegroup",
                                                options=[
                                                    {"label": val, "value": val}
                                                    for val in literal_to_list(TimeGroup)
                                                ],
                                                value="Seasonal",
                                            ),
                                        ],
                                        width=4,
                                    ),
                                    dbc.Col(
                                        [
                                            html.Label(
                                                "AGGREGATION:",
                                                style={"fontWeight": "bold", "fontSize": "0.9em"},
                                            ),
                                            dcc.Dropdown(
                                                id="scenario-seasonal-lines-agg",
                                                options=[
                                                    {"label": val, "value": val}
                                                    for val in literal_to_list(TimeGroupAgg)
                                                ],
                                                value="Average Day",
                                                clearable=False,
                                            ),
                                        ],
                                        width=2,
                                    ),
                                    dbc.Col(
                                        [
                                            html.Label(
                                                "WEATHER VAR:",
                                                style={"fontWeight": "bold", "fontSize": "0.9em"},
                                            ),
                                            dcc.Dropdown(
                                                id="scenario-seasonal-lines-weather",
                                                options=[
                                                    {"label": val, "value": val}
                                                    for val in literal_to_list(WeatherVar)
                                                ],
                                                value="Temperature",
                                                clearable=False,
                                            ),
                                        ],
                                        width=3,
                                    ),
                                ],
                                align="center",
                            )
                        ]
                    ),
                    dbc.CardBody([dcc.Graph(id="scenario-seasonal-lines-plot")]),
                ],
                className="mb-4",
            ),
            # Seasonal Load Area
            dbc.Card(
                [
                    dbc.CardHeader(
                        [
                            dbc.Row(
                                [
                                    dbc.Col(
                                        [html.H4("Seasonal Load Area", className="mb-0")], width=2
                                    ),
                                    dbc.Col(
                                        [
                                            html.Label(
                                                "BREAKDOWN:",
                                                style={"fontWeight": "bold", "fontSize": "0.9em"},
                                            ),
                                            dcc.Dropdown(
                                                id="scenario-seasonal-area-breakdown",
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
                                                value="Sector",
                                                clearable=False,
                                            ),
                                        ],
                                        width=3,
                                    ),
                                    dbc.Col(
                                        [
                                            html.Label(
                                                "YEAR:",
                                                style={"fontWeight": "bold", "fontSize": "0.9em"},
                                            ),
                                            dcc.Dropdown(
                                                id="scenario-seasonal-area-year",
                                                options=[
                                                    {"label": str(year), "value": year}
                                                    for year in years
                                                ],
                                                value=years[0] if years else None,
                                                clearable=False,
                                            ),
                                        ],
                                        width=2,
                                    ),
                                    dbc.Col(
                                        [
                                            html.Label(
                                                "TIME GROUP AGG:",
                                                style={"fontWeight": "bold", "fontSize": "0.9em"},
                                            ),
                                            dcc.Dropdown(
                                                id="scenario-seasonal-area-agg",
                                                options=[
                                                    {"label": val, "value": val}
                                                    for val in literal_to_list(TimeGroupAgg)
                                                ],
                                                value="Average Day",
                                                clearable=False,
                                            ),
                                        ],
                                        width=2,
                                    ),
                                    dbc.Col(
                                        [
                                            html.Label(
                                                "TIME GROUP:",
                                                style={"fontWeight": "bold", "fontSize": "0.9em"},
                                            ),
                                            dcc.RadioItems(
                                                id="scenario-seasonal-area-timegroup",
                                                options=[
                                                    {"label": val, "value": val}
                                                    for val in literal_to_list(TimeGroup)
                                                ],
                                                value="Seasonal",
                                            ),
                                        ],
                                        width=3,
                                    ),
                                ],
                                align="center",
                                className="mb-2",
                            ),
                            dbc.Row(
                                [
                                    dbc.Col(
                                        [
                                            html.Label(
                                                "WEATHER VAR:",
                                                style={"fontWeight": "bold", "fontSize": "0.9em"},
                                            ),
                                            dcc.Dropdown(
                                                id="scenario-seasonal-area-weather",
                                                options=[
                                                    {"label": val, "value": val}
                                                    for val in literal_to_list(WeatherVar)
                                                ],
                                                value="Temperature",
                                                clearable=False,
                                            ),
                                        ],
                                        width=3,
                                    )
                                ],
                                align="center",
                            ),
                        ]
                    ),
                    dbc.CardBody([dcc.Graph(id="scenario-seasonal-area-plot")]),
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
                                                "Select Years:", style={"fontWeight": "bold"}
                                            ),
                                            create_styled_checklist(
                                                [str(year) for year in years],
                                                "scenario-load-duration-years",
                                                [str(years[0])] if years else [],
                                            ),
                                        ],
                                        width=12,
                                    )
                                ],
                                className="mb-3",
                            ),
                            dcc.Graph(id="scenario-load-duration-plot"),
                        ]
                    ),
                ],
                className="mb-4",
            ),
        ]
    )  # Close the main html.Div
