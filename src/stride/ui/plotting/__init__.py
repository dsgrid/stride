from typing import TYPE_CHECKING, Any

import pandas as pd
import plotly.graph_objects as go

from . import facets, simple

if TYPE_CHECKING:
    from stride.ui.color_manager import ColorManager


class StridePlots:
    def __init__(self, color_generator: "ColorManager", template: str = "plotly_white"):
        """
        Initialize StridePlots with a color generator function.

        Parameters
        ----------
        color_generator : ColorManager
            Function that takes a string key and returns a color value
        template : str
            Plotly template name (e.g., 'plotly_white', 'plotly_dark')
        """
        self._color_generator = color_generator
        self._template = template

    def set_template(self, template: str) -> None:
        """
        Set the plotly template for all plots.

        Parameters
        ----------
        template : str
            Plotly template name (e.g., 'plotly_white', 'plotly_dark')
        """
        self._template = template

    def get_template(self) -> str:
        """
        Get the current plotly template.

        Returns
        -------
        str
            Current template name
        """
        return self._template

    def grouped_single_bars(
        self,
        df: pd.DataFrame,
        group: str,
        use_color_manager: bool = True,
        fixed_color: str | None = None,
    ) -> go.Figure:
        """Create a bar plot with 2 levels of x axis."""
        fig = simple.grouped_single_bars(
            df,
            group,
            self._color_generator,
            use_color_manager=use_color_manager,
            fixed_color=fixed_color,
        )
        fig.update_layout(template=self._template)
        return fig

    def grouped_multi_bars(
        self, df: pd.DataFrame, x_group: str = "scenario", y_group: str = "end_use"
    ) -> go.Figure:
        """Create grouped and multi-level bar chart."""
        fig = simple.grouped_multi_bars(df, self._color_generator, x_group, y_group)
        fig.update_layout(template=self._template)
        return fig

    def grouped_stacked_bars(
        self,
        df: pd.DataFrame,
        year_col: str = "year",
        group_col: str = "scenario",
        stack_col: str = "metric",
        value_col: str = "demand",
        show_scenario_indicators: bool = True,
    ) -> go.Figure:
        """Create grouped and stacked bar chart."""
        fig = simple.grouped_stacked_bars(
            df,
            self._color_generator,
            year_col,
            group_col,
            stack_col,
            value_col,
            show_scenario_indicators,
        )
        fig.update_layout(template=self._template)
        return fig

    def time_series(
        self, df: pd.DataFrame, group_by: str | None = None, chart_type: str = "Line"
    ) -> go.Figure:
        """Plot time series data for multiple years of a single scenario."""
        fig = simple.time_series(df, self._color_generator, group_by, chart_type)
        fig.update_layout(template=self._template)
        return fig

    def demand_curve(self, df: pd.DataFrame) -> go.Figure:
        """Create a load duration curve plot."""
        fig = simple.demand_curve(df, self._color_generator)
        fig.update_layout(template=self._template)
        return fig

    def area_plot(self, df: pd.DataFrame, scenario_name: str, metric: str = "demand") -> go.Figure:
        """Create a stacked area plot for a single scenario."""
        fig = simple.area_plot(df, self._color_generator, scenario_name, metric)
        fig.update_layout(template=self._template)
        return fig

    def faceted_time_series(
        self,
        df: pd.DataFrame,
        chart_type: str = "Line",
        group_by: str | None = None,
        value_col: str = "value",
    ) -> go.Figure:
        """Create faceted subplots for each scenario with shared legend."""
        fig = facets.faceted_time_series(
            df, self._color_generator, chart_type, group_by, value_col
        )
        fig.update_layout(template=self._template)
        return fig

    def seasonal_load_lines(self, df: pd.DataFrame) -> go.Figure:
        """Create faceted subplots for seasonal load lines."""
        fig = facets.seasonal_load_lines(df, self._color_generator)
        fig.update_layout(template=self._template)
        return fig

    def seasonal_load_area(self, df: pd.DataFrame) -> go.Figure:
        """Create faceted area charts for seasonal load patterns."""
        fig = facets.seasonal_load_area(df, self._color_generator)
        fig.update_layout(template=self._template)
        return fig
