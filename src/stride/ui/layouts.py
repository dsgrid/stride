from dash import html, dcc, Input, State, Output, callback
import time

from components import Components
from constants import LIGHT_GRAY_1, CLICK_TIME_MS
from data_handler import DataHandler
from plotting import StridePlots


def home_page_layout(
    components: Components,
    data_handler: DataHandler,
    plotter: StridePlots,
) -> html.Div:
    scenarios = data_handler.scenarios
    end_uses = data_handler.end_uses
    years = data_handler.years

    left_axis_options = [
        "Annual Energy Consumption",
        "Annual Energy Consumption by Sector",
        "Annual Energy Consumption by End Use",
    ]
    right_axis_options = ["None"] + left_axis_options
    left_axis = "LEFT Y AXIS"
    right_axis = "RIGHT Y AXIS (optional)"
    axis_bar_1 = components.dropdown_bar(
        "axis-1", left_axis, left_axis_options, right_axis, right_axis_options
    )
    axis_bar_2 = components.dropdown_bar(
        "axis-2", left_axis, left_axis_options, right_axis, right_axis_options
    )
    axis_bar_3 = components.dropdown_bar("axis-3", "YEAR", years)
    axis_bar_4 = components.dropdown_bar(
        "axis-4",
        "CHART TYPE",
        ["Area"],
        right_axis,
        [
            "None",
            "Percent EV Adoption",
            "GDP",
            "GDP Per Capita",
            "Human Development Index",
            "Stock",
        ],
        left_axis,
        left_axis_options,
    )
    layout = html.Div(
        [
            html.Div(
                [
                    html.H2(
                        children="Combined Charts",
                        style={"textAlign": "left", "padding": "5px"},
                    ),
                    axis_bar_1,
                    dcc.Graph(
                        id="graph-1",
                        style={
                            "margin": "0px 20px",
                            "padding": "10px 10px 0px",
                            "backgroundColor": LIGHT_GRAY_1,
                        },
                    ),
                    components.button_bar("scenarios-1", scenarios, add_numbers=True),
                ],
                style={"marginBottom": 5},
            ),
            html.Div(
                [
                    axis_bar_2,
                    dcc.Graph(
                        id="graph-2",
                        style={
                            "margin": "0px 20px",
                            "padding": "10px 10px 0px",
                            "backgroundColor": LIGHT_GRAY_1,
                        },
                    ),
                    components.button_bar("end-uses-1", end_uses),
                    components.button_bar("scenarios-2", scenarios, disable_square=True, add_numbers=True),
                ],
                style={"marginBottom": 5},
            ),
            html.Div(
                [
                    axis_bar_3,
                    dcc.Graph(
                        id="graph-3",
                        style={
                            "margin": "0px 20px",
                            "padding": "10px 10px 0px",
                            "backgroundColor": LIGHT_GRAY_1,
                        },
                    ),
                    components.button_bar("scenarios-3", scenarios),
                ],
                style={"marginBottom": 5},
            ),
            html.Div(
                [
                    axis_bar_4,
                    components.button_bar("end-uses-2", end_uses),
                    components.comparison_plots("comparison_plot"),
                ]
            ),
        ],
        style={"display": "inline"},
        id="home_page",
     )

    register_callbacks(scenarios, components, plotter, data_handler)

    return layout

def register_callbacks(scenarios: list[str], components: Components, plotter: StridePlots, data_handler: DataHandler):

    @callback(
        Output("graph-1", "figure"),
        [Input(button_id, "n_clicks") for button_id in components.button_bars["scenarios-1"]],
        State("graph-1", "figure"),
    )
    def update_graph_1(*args):
        time.sleep(CLICK_TIME_MS / 1500)
        n_clicks = args[:-1]
        names = [components.button_id_name[button_id] for button_id in components.button_bars["scenarios-1"]]
        selected_scenarios = list(
            map(lambda x: x[0], filter(lambda x: x[1] == 0, zip(names, n_clicks)))
        )
        if len(selected_scenarios) == 0:
            return args[-1]
        df = data_handler.sector_df(scenarios=selected_scenarios)
        return plotter.grouped_single_bars(df, "scenario")  # type: ignore


    @callback(
        Output("graph-2", "figure"),
        [Input(button_id, "n_clicks") for button_id in components.button_bars["scenarios-2"]],
        [Input(button_id, "n_clicks") for button_id in components.button_bars["end-uses-1"]],
        State("graph-2", "figure"),
    )
    def update_graph_2(*args):
        time.sleep(CLICK_TIME_MS / 1500)
        scenario_names = [
            components.button_id_name[button_id] for button_id in components.button_bars["scenarios-2"]
        ]
        end_use_names = [
            components.button_id_name[button_id] for button_id in components.button_bars["end-uses-1"]
        ]

        args_list = list(args)
        scenario_n_clicks = [args_list.pop(0) for _ in range(len(scenario_names))]
        end_uses_n_clicks = [args_list.pop(0) for _ in range(len(end_use_names))]

        selected_scenarios = list(
            map(
                lambda x: x[0],
                filter(lambda x: x[1] == 0, zip(scenario_names, scenario_n_clicks)),
            )
        )
        selected_end_uses = list(
            map(
                lambda x: x[0],
                filter(lambda x: x[1] == 0, zip(end_use_names, end_uses_n_clicks)),
            )
        )

        if len(selected_scenarios) == 0 or len(selected_end_uses) == 0:
            return args[-1]

        df = data_handler.sector_df(scenarios=selected_scenarios, end_uses=selected_end_uses)
        return plotter.grouped_multi_bars(df)


    @callback(
        Output("graph-3", "figure"),
        [Input(button_id, "n_clicks") for button_id in components.button_bars["scenarios-3"]],
        Input("axis-3_dropdown-1", "value"),
        State("graph-3", "figure"),
    )
    def update_graph_3(*args):
        time.sleep(CLICK_TIME_MS / 1500)
        scenario_names = [
            components.button_id_name[button_id] for button_id in components.button_bars["scenarios-2"]
        ]

        args_list = list(args)
        scenario_n_clicks = [args_list.pop(0) for _ in range(len(scenario_names))]
        year = args_list.pop(0)

        selected_scenarios = list(
            map(
                lambda x: x[0],
                filter(lambda x: x[1] == 0, zip(scenario_names, scenario_n_clicks)),
            )
        )

        if len(selected_scenarios) == 0:
            return args[-1]

        df = data_handler.duration_df(scenarios=selected_scenarios, years=[year])
        return plotter.demand_curve(df)  # type: ignore

    for idx, scenario in enumerate(scenarios):
        @callback(
            Output(f"comparison_plot_{idx}", "figure"),
            [Input(button_id, "n_clicks") for button_id in components.button_bars["end-uses-2"]],
        )
        def update_comarison_fig(*n_clicks):
            end_use_names = [
                components.button_id_name[button_id] for button_id in components.button_bars["end-uses-2"]
            ]
            selected_end_uses = list(
                map(
                    lambda x: x[0],
                    filter(lambda x: x[1] == 0, zip(end_use_names, n_clicks)),
                )
            )
            df = data_handler.sector_df(end_uses=selected_end_uses)
            return plotter.area_plot(df, scenario)

    components.connect_button_bars(["scenarios-1", "scenarios-2", "scenarios-3"])

