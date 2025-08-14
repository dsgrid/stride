from typing import Callable
import pandas as pd
import plotly.graph_objects as go

from . import simple, facets


class StridePlots:
    def __init__(self, color_generator: Callable[[str], str]):
        """
        Initialize StridePlots with a color generator function.

        Parameters
        ----------
        color_generator : Callable[[str], str]
            Function that takes a string key and returns a color value
        """
        self._color_generator = color_generator

    def grouped_single_bars(
        self, df: pd.DataFrame, group: str, use_color_manager=True
    ) -> go.Figure:
        """Create a bar plot with 2 levels of x axis."""
        return simple.grouped_single_bars(df, group, self._color_generator, use_color_manager)

    def grouped_multi_bars(
        self, df: pd.DataFrame, x_group: str = "scenario", y_group: str = "end_use"
    ):
        """Create grouped and multi-level bar chart."""
        return simple.grouped_multi_bars(df, self._color_generator, x_group, y_group)

    def grouped_stacked_bars(
        self,
        df: pd.DataFrame,
        year_col: str = "year",
        group_col: str = "scenario",
        stack_col: str = "metric",
        value_col: str = "demand",
    ) -> go.Figure:
        """Create grouped and stacked bar chart."""
        return simple.grouped_stacked_bars(
            df, self._color_generator, year_col, group_col, stack_col, value_col
        )

    def time_series(
        self, df: pd.DataFrame, group_by: str = None, chart_type: str = "Line"
    ) -> go.Figure:
        """Plot time series data for multiple years of a single scenario."""
        return simple.time_series(df, self._color_generator, group_by, chart_type)

    def demand_curve(self, df: pd.DataFrame):
        """Create a load duration curve plot."""
        return simple.demand_curve(df, self._color_generator)

    def area_plot(self, df: pd.DataFrame, scenario_name: str, metric: str = "demand"):
        """Create a stacked area plot for a single scenario."""
        return simple.area_plot(df, self._color_generator, scenario_name, metric)

    def faceted_time_series(
        self,
        df: pd.DataFrame,
        chart_type: str = "Line",
        group_by: str = None,
        value_col: str = "value",
    ):
        """Create faceted subplots for each scenario with shared legend."""
        return facets.faceted_time_series(
            df, self._color_generator, chart_type, group_by, value_col
        )

    def seasonal_load_lines(self, df: pd.DataFrame):
        """Create faceted subplots for seasonal load lines."""
        return facets.seasonal_load_lines(df, self._color_generator)

    def seasonal_load_area(self, df: pd.DataFrame) -> go.Figure:
        """Create faceted area charts for seasonal load patterns."""
        return facets.seasonal_load_area(df, self._color_generator)

    # Deprecated method names for backward compatibility
    def _seasonal_load_lines(self, df: pd.DataFrame):
        """Deprecated: Use seasonal_load_lines instead."""
        return self.seasonal_load_lines(df)

    def _seasonal_load_area(self, df: pd.DataFrame) -> go.Figure:
        """Deprecated: Use seasonal_load_area instead."""
        return self.seasonal_load_area(df)

    def _add_seasonal_line_traces(self, fig, df, layout_config):
        """Deprecated: This is now handled internally."""
        from .facets import add_seasonal_line_traces

        return add_seasonal_line_traces(fig, df, layout_config, self._color_generator)
