from typing import Callable
import numpy as np
import pandas as pd
import plotly.graph_objects as go

TRANSPARENT = "rgba(0, 0, 0, 0)"


class StridePlots:
    def __init__(self, color_generator: Callable[[str], str]):
        self._color_generator = color_generator

    def grouped_single_bars(self, df: pd.DataFrame, group: str) -> go.Figure:
        """
        Creates a bar plot with 2 levels of x axis
        """

        df = _aggregate_scenario_year(df)
        fig = go.Figure()

        years = df["year"].unique()
        df_grouped = df[group].unique()
        for group_value in df_grouped:
            df_subset = df[df[group] == group_value]
            fig.add_trace(
                go.Bar(
                    x=df_subset["year"],
                    y=df_subset["demand"],
                    name=group_value,
                    marker_color=self._color_generator(group_value),
                    showlegend=False,
                )
            )

        fig.update_layout(
            plot_bgcolor=TRANSPARENT,  # Sets the plot area background color
            paper_bgcolor=TRANSPARENT,  # Sets the surrounding paper background color
            margin_b=0,
            margin_t=20,
            margin_l=20,
            margin_r=20,
            barmode="group",
        )

        n_groups = len(years)
        n_bars = len(df_grouped)
        fig = numbers_under_each_bar(fig, n_groups, n_bars)

        return fig

    def grouped_multi_bars(
        self, df: pd.DataFrame, x_group: str = "scenario", y_group: str = "end_use"
    ):
        bars = []
        for x_value in df[x_group].unique():
            for y_value in df[y_group].unique():
                df_subset = df[(df[x_group] == x_value) & (df[y_group] == y_value)]
                bars.append(
                    go.Bar(
                        x=df_subset["year"],
                        y=df_subset["demand"],
                        marker_color=self._color_generator(y_value),
                        name=y_value,
                        offsetgroup=x_value,
                        showlegend=False,
                    )
                )

        fig = go.Figure(data=bars)
        fig.update_layout(
            plot_bgcolor=TRANSPARENT,  # Sets the plot area background color
            paper_bgcolor=TRANSPARENT,  # Sets the surrounding paper background color
            margin_b=0,
            margin_t=20,
            margin_l=20,
            margin_r=20,
            barmode="stack",
        )
        n_groups = len(df["year"].unique())
        n_bars = len(df[x_group].unique())
        fig = numbers_under_each_bar(fig, n_groups, n_bars)

        return fig

    def demand_curve(self, df: pd.DataFrame):
        fig = go.Figure()
        for scenario in df["scenario"].unique():
            df_scenario = df[df["scenario"] == scenario]
            fig.add_trace(
                go.Scatter(
                    x=df_scenario["hours"],
                    y=df_scenario["demand"],
                    mode="lines",
                    marker=dict(color=self._color_generator(scenario)),
                    name=scenario,
                    showlegend=False,
                )
            )
        fig.update_layout(
            plot_bgcolor=TRANSPARENT,  # Sets the plot area background color
            paper_bgcolor=TRANSPARENT,  # Sets the surrounding paper background color
            margin_b=0,
            margin_t=20,
            margin_l=20,
            margin_r=20,
            barmode="stack",
        )
        return fig

    def area_plot(
        self, df: pd.DataFrame, scenario_name: str, metric: str = "demand"
    ) -> go.Figure:
        fig = go.Figure()
        for end_use in df["end_use"].unique():
            end_use_df = df[df["end_use"] == end_use]
            fig.add_trace(go.Scatter(
                x=end_use_df["year"],
                y=end_use_df[metric],
                mode="lines",
                line=dict(color=self._color_generator(end_use)),
                showlegend=False,
                stackgroup="one",
            ))
        fig.update_layout(title=scenario_name)

        fig.update_layout(
            plot_bgcolor=TRANSPARENT,  # Sets the plot area background color
            paper_bgcolor=TRANSPARENT,  # Sets the surrounding paper background color
            margin_b=50,
            margin_t=50,
            margin_l=10,
            margin_r=10,
        )

        return fig


def _aggregate_scenario_year(df: pd.DataFrame):
    return df.groupby(["year", "scenario"])["demand"].sum().reset_index()


def numbers_under_each_bar(
    fig: go.Figure, n_groups: int, n_bars: int, sep_width: float = 0.2
) -> go.Figure:
    for bar_group_num in range(1, n_groups + 1):
        bar_nums = np.arange(n_bars) + 1
        x = (np.arange(n_bars) - ((n_bars - 1) / 2)) * ((1 - sep_width) / n_bars)
        x = x + bar_group_num - 1
        for bar_num, xi in zip(bar_nums, x):
            fig.add_annotation(
                text=f"<b>{bar_num}</b>",
                y=0,
                x=xi,
                showarrow=False,
                yshift=-10,
            )
    return fig
