from dash import html, callback, Output, Input, State, ctx, dcc
import dash_bootstrap_components as dbc
from collections import defaultdict
from typing import Callable
import time
import re

from constants import LIGHT_GRAY_2, LIGHT_GRAY_1, CLICK_TIME_MS
from utils import rgba_to_str, str_to_rgba

class Components:
    def __init__(self, scenarios: list[str], color_generator: Callable):
        self.button_bars = defaultdict(list)
        self.button_id_name = {}
        self.button_click_time_ms = {}
        self.color_generator = color_generator
        self.scenarios = scenarios
        self.scenario_numbers = {k: idx + 1 for idx, k in enumerate(scenarios)}


    def create_navbar(self) -> html.Div:
        navbar = html.Div(
            dbc.Row(
                [
                    dbc.Col(dbc.Button("Home", id="nav-home", class_name="rounded-0", n_clicks=1), width="auto"),
                    *[
                        dbc.Col(
                            dbc.Button(scenario, id=f"nav-scenario-{idx+1}", class_name="rounded-0 nav-button-off", n_clicks=0),
                            width="auto",
                        )
                        for idx, scenario in enumerate(self.scenarios)
                    ],
                ],
                style={"backgroundColor": "rgba(128, 128, 128, .2)"},
                justify="center",
            ),
        )

        nav_bars = ["nav-home", *[f"nav-scenario-{idx+1}" for idx in range(len(self.scenarios))]]
        @callback(
            [
                *[Output(bar, "n_clicks") for bar in nav_bars],
                *[Output(bar, "class_name") for bar in nav_bars],
            ],
            *[Input(bar, "n_clicks") for bar in nav_bars],
        )
        def navigate(*args):
            n_clicks = args
            if ctx.triggered_id is not None:
                triggered_idx = nav_bars.index(ctx.triggered_id)
                n_clicks = [0 for _ in range(len(nav_bars))]
                n_clicks[triggered_idx] = 1

            def class_from_n_clicks(n_clicks):
                return ["rounded-0 nav-button-on" if n == 1 else "rounded-0 nav-button-off" for n in n_clicks]
            
            r = (*n_clicks, *class_from_n_clicks(n_clicks))
            return r

        @callback(
            Output("home_page", "style"),
            [Input(bar, "n_clicks") for bar in nav_bars],
        )
        def toggle_home_page(*n_clicks):
            if n_clicks[0] == 1:
                return {"display": "inline"}
            return {"display": "None"}

        return navbar


    @staticmethod
    def dropdown_bar(
        bar_name: str,
        left_dropdown_name: str,
        left_dropdown_opts: list[str],
        right_dropdown_name: str | None = None,
        right_dropdown_opts: list[str] | None = None,
        second_left_dropdown_name: str | None = None,
        second_left_dropdown_opts: list[str] | None = None,
    ):
        axis_elements = []
        left_axis_col = dbc.Col(
            dbc.Row(
                [
                    dbc.Col(left_dropdown_name, width="auto", align="start"),
                    dbc.Col(
                        html.Div(
                            dcc.Dropdown(
                                left_dropdown_opts,
                                left_dropdown_opts[0],
                                id=f"{bar_name}_dropdown-1",
                                style={"white-space": "nowrap"},
                            ),
                        ),
                        width=7,
                        align="start",
                    ),
                ],
                justify="start",
            ),
            width=6,
        )

        axis_elements.append(left_axis_col)

        if right_dropdown_name is not None and right_dropdown_opts is not None:
            right_axis_col = dbc.Col(
                dbc.Row(
                    [
                        dbc.Col(right_dropdown_name, width="auto"),
                        dbc.Col(
                            html.Div(
                                dcc.Dropdown(
                                    right_dropdown_opts,
                                    right_dropdown_opts[0],
                                    id=f"{bar_name}_dropdown-2",
                                    style={"white-space": "nowrap"},
                                ),
                            ),
                            width=7,
                        ),
                    ],
                    justify="end",
                ),
                width=6,
            )
            axis_elements.append(right_axis_col)
        else:
            axis_elements.append(None)

        if second_left_dropdown_name is not None and second_left_dropdown_opts is not None:
            right_axis_col = dbc.Col(
                dbc.Row(
                    [
                        dbc.Col(second_left_dropdown_name, width="auto"),
                        dbc.Col(
                            html.Div(
                                dcc.Dropdown(
                                    second_left_dropdown_opts,
                                    second_left_dropdown_opts[0],
                                    id=f"{bar_name}_dropdown-3",
                                    style={"white-space": "nowrap"},
                                ),
                            ),
                            width=7,
                        ),
                    ],
                    justify="start",
                ),
                width=6,
                align="left",
            )
            axis_elements.append(right_axis_col)
        else:
            axis_elements.append(None)

        row_1 = (
            dbc.Row(axis_elements[:2])
            if axis_elements[1] is not None
            else dbc.Row(axis_elements[0])
        )
        row_2 = dbc.Row(axis_elements[2]) if axis_elements[2] is not None else None
        children = [row_1, row_2] if row_2 is not None else row_1

        bar = html.Div(
            children=children,
            style={
                "margin": "0px 20px",
                "padding": "10px 10px 10px",
                "backgroundColor": LIGHT_GRAY_2,
            },
        )

        return bar


    @staticmethod
    def button_with_colored_square(
        name: str,
        color: str,
        button_id: str,
        disable_square: bool = False,
        add_number: int | None = None,
    ):
        """
        Creates a square Div with the hex color provided,
        returns a dbc Col containing a button with the square and name
        """

        colored_square = html.Div(
            style={
                "width": "10px",
                "height": "10px",
                "padding": "5px",
                "margin": "7px",
                "background-color": color,
                "display": "none" if disable_square else "inline",
            },
            id=f"{button_id}_square",
        )

        number_div = []
        if add_number is not None:
            number_div.append(
                html.B(
                    str(add_number) + " ",
                    style={"margin": "0px", "padding": "0px", "width": "18px"},
                )
            )

        return dbc.Col(
            dbc.Button(
                dbc.Row(
                    [
                        colored_square,
                        *number_div,
                        name,
                    ],
                    justify="start",
                ),
                id=button_id,
                n_clicks=0,
            ),
        )


    def button_bar(
        self,
        bar_name: str,
        names: list[str],
        add_numbers: bool = False,
        disable_square: bool = False,
    ):
        bar_name = bar_name.replace(" ", "-").replace("_", "-")

        buttons = []
        for btn_name in names:
            kwargs = {}
            if add_numbers:
                kwargs["add_number"] = self.scenario_numbers[btn_name]
            if disable_square:
                kwargs["disable_square"] = True
            # TODO, create function for button init
            button_color = self.color_generator(btn_name)
            btn_id_name = btn_name.replace(" ", "-").replace("_", "-")
            button_id = f"bar_name={bar_name}_btn_name={btn_id_name}"
            self.button_id_name[button_id] = btn_name
            buttons.append(
                dbc.Col(
                    self.button_with_colored_square(btn_name, button_color, button_id, **kwargs),
                    width="auto",
                )
            )
            self.button_bars[bar_name].append(button_id)
            self.button_click_time_ms[button_id] = time.time() * 1000

            @callback(
                [
                    Output(button_id, "class_name"),
                    Output(f"{button_id}_square", "style"),
                    Output(button_id, "n_clicks", allow_duplicate=True),
                ],
                [
                    Input(button_id, "n_clicks"),
                ],
                [State(f"{button_id}_square", "style")],
                prevent_initial_call="initial_duplicate",
            )
            def toggle_click(n_clicks, square_style):
                rgba = list(str_to_rgba(square_style["background-color"]))
                n_clicks = n_clicks % 2

                if n_clicks == 0:
                    rgba[3] = 1.0
                    square_style["background-color"] = rgba_to_str(*rgba)
                    return "button-on", square_style, 0

                else:
                    rgba[3] = 0.25
                    square_style["background-color"] = rgba_to_str(*rgba)
                    return "button-off", square_style, 1

        button_ids = self.button_bars[bar_name]

        # Register all buttons in bar with doubleclick mechanics
        # This *should* get called before toggle_click
        @callback(
            [
                Output(button_id, "n_clicks", allow_duplicate=True)
                for button_id in button_ids
            ],
            # passing the disabled attribute from this callback forces it to come before the
            # connecting bars callback
            [Output(button_id, "disabled") for button_id in button_ids],
            [Input(button_id, "n_clicks_timestamp") for button_id in button_ids],
            [State(button_id, "n_clicks") for button_id in button_ids],
            prevent_initial_call="initial_duplicate",
        )
        def toggle_double_click(*args):
            nonlocal button_ids

            assert len(args) % 2 == 0, "Invalid inputs for double click callback"
            n_inputs = len(args) // 2
            inputs = args[:n_inputs]
            states = args[n_inputs:]

            buttons_disabled = [False for _ in range(len(states))]

            triggered_id = ctx.triggered_id
            if triggered_id is None:
                return [*states, *buttons_disabled]

            button_idx = button_ids.index(triggered_id)

            if inputs[button_idx] - self.button_click_time_ms[triggered_id] > CLICK_TIME_MS:
                # Not a double click, return the current state
                self.button_click_time_ms[triggered_id] = inputs[button_idx]
                output = states

            else:
                # double click registered
                disabled_buttons = [1 for _ in range(len(button_ids))]

                if all(b >= 1 for b in states):
                    output = [0 for _ in range(len(button_ids))]

                else:
                    disabled_buttons[button_idx] = 0
                    output = disabled_buttons

                self.button_click_time_ms[triggered_id] = inputs[button_idx] - CLICK_TIME_MS * 2

            return [*output, *buttons_disabled]

        return html.Div(
            dbc.Row(
                buttons,
                justify="center",
                style={"backgroundColor": LIGHT_GRAY_1, "margin": "0px 20px"},
                id=bar_name,
            ),
        )


    @staticmethod
    def bar_name_from_id(button_id: str) -> tuple[str, str]:
        btn_name = re.search(r"btn_name=([a-zA-Z\-1-9]*)", button_id)
        bar_name = re.search(r"bar_name=([a-zA-Z\-1-9]*)", button_id)
        if btn_name is not None and bar_name is not None:
            return btn_name.groups()[0], bar_name.groups()[0]
        raise ValueError(f"Invalid button id {button_id}")


    def connect_button_bars(self, bar_names: list[str]):
        # For now assume the bars have the same names in the same orders
        button_ids = sum((self.button_bars[bar_name] for bar_name in bar_names), [])

        @callback(
            [
                Output(button_id, "n_clicks", allow_duplicate=True)
                for button_id in button_ids
            ],
            [Input(button_id, "n_clicks") for button_id in button_ids],
            [Input(button_id, "disabled") for button_id in button_ids],
            prevent_initial_call="initial_duplicate",
        )
        def connect_button_bars(*args):
            nonlocal bar_names
            nonlocal button_ids
            n_buttons = len(button_ids) // len(bar_names)
            n_bars = len(bar_names)
            args = args[: n_buttons * n_bars]
            triggered_id = ctx.triggered_id

            if triggered_id is None:
                return args

            _, triggered_bar = self.bar_name_from_id(triggered_id)
            bar_idx = bar_names.index(triggered_bar)

            updated_state = args[bar_idx * n_buttons : (bar_idx + 1) * n_buttons]
            duplicated_state = sum((list(updated_state) for _ in range(len(bar_names))), [])
            return duplicated_state


    def comparison_plots(self, id_prefix: str):
        """creates comparison plots for all scenarios."""

        figs = []
        for idx, scenario in enumerate(self.scenarios):
            if len(figs) == 0 or len(figs[-1]) == 0:
                figs.append([
                    dbc.Col(
                        dcc.Graph(
                            id=f"{id_prefix}_{idx}",
                        ),
                        width=6,
                    )
                ])

            else:
                figs[-1].append(
                    dbc.Col(
                        dcc.Graph(
                            id=f"{id_prefix}_{idx}",
                            # figure=fig,
                        ),
                        width=6,
                    )
                )

        figs = [dbc.Row(ff) for ff in figs]
        return html.Div(figs, style={
            "backgroundColor": LIGHT_GRAY_1,
            "margin": "0px 20px",
        })

