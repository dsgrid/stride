from typing import TYPE_CHECKING, Any
import pandas as pd
import plotly.graph_objects as go

from . import simple, facets

if TYPE_CHECKING:
    from stride.ui.color_manager import ColorManager


class StridePlots:
    def __init__(self, color_generator: "ColorManager"):
        """
        Initialize StridePlots with a color generator function.

        Parameters
        ----------
        color_generator : ColorManager
            Function that takes a string key and returns a color value
        """
        self._color_generator = color_generator

    def grouped_single_bars(
        self, df: pd.DataFrame, group: str, use_color_manager: bool = True
    ) -> go.Figure:
        """Create a bar plot with 2 levels of x axis."""
        return simple.grouped_single_bars(df, group, self._color_generator, use_color_manager)

    def grouped_multi_bars(
        self, df: pd.DataFrame, x_group: str = "scenario", y_group: str = "end_use"
    ) -> go.Figure:
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
        self, df: pd.DataFrame, group_by: str | None = None, chart_type: str = "Line"
    ) -> go.Figure:
        """Plot time series data for multiple years of a single scenario."""
        return simple.time_series(df, self._color_generator, group_by, chart_type)

    def demand_curve(self, df: pd.DataFrame) -> go.Figure:
        """Create a load duration curve plot."""
        return simple.demand_curve(df, self._color_generator)

    def area_plot(self, df: pd.DataFrame, scenario_name: str, metric: str = "demand") -> go.Figure:
        """Create a stacked area plot for a single scenario."""
        return simple.area_plot(df, self._color_generator, scenario_name, metric)

    def faceted_time_series(
        self,
        df: pd.DataFrame,
        chart_type: str = "Line",
        group_by: str | None = None,
        value_col: str = "value",
    ) -> go.Figure:
        """Create faceted subplots for each scenario with shared legend."""
        return facets.faceted_time_series(
            df, self._color_generator, chart_type, group_by, value_col
        )

    def seasonal_load_lines(self, df: pd.DataFrame) -> go.Figure:
        """Create faceted subplots for seasonal load lines."""
        return facets.seasonal_load_lines(df, self._color_generator)

    def seasonal_load_area(self, df: pd.DataFrame) -> go.Figure:
        """Create faceted area charts for seasonal load patterns."""
        return facets.seasonal_load_area(df, self._color_generator)
