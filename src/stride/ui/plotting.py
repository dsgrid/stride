from typing import Callable
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

TRANSPARENT = "rgba(0, 0, 0, 0)"
DEFAULT_BAR_COLOR = "rgba(0,0,200,0.8)"

class StridePlots:
    def __init__(self, color_generator: Callable[[str], str]):
        self._color_generator = color_generator

    def grouped_single_bars(self, df: pd.DataFrame, group: str, use_color_manager=True) -> go.Figure:
        """
        Creates a bar plot with 2 levels of x axis
        """

        fig = go.Figure()

        years = df["year"].unique()
        df_grouped = df[group].unique()
        for group_value in df_grouped:
            df_subset = df[df[group] == group_value]

            color = DEFAULT_BAR_COLOR
            if use_color_manager:
                color = self._color_generator.get_color(str(group_value))

            fig.add_trace(
                go.Bar(
                    x=df_subset["year"].astype(str),
                    y=df_subset["value"],
                    name=str(group_value),  # Convert to string to handle numpy int64
                    marker_color=color,
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
                        x=df_subset["year"].astype(str),
                        y=df_subset["value"],
                        marker_color=self._color_manager.get_color(y_value),
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

    def grouped_stacked_bars(
        self, df: pd.DataFrame,
        year_col: str = "year",
        group_col: str = "scenario",
        stack_col: str = "end_use",
        value_col: str = "demand"
    ) -> go.Figure:
        """
        Creates grouped and stacked bar chart:
        - Groups by year (x-axis positions)
        - Each group contains multiple bar stacks (one per scenario)
        - Each stack is colored by sector/end_use
        """
        fig = go.Figure()

        years = sorted(df[year_col].unique())
        groups = sorted(df[group_col].unique())
        stack_categories = sorted(df[stack_col].unique())

        # Create traces for each combination of group and stack category
        for group in groups:
            for stack_cat in stack_categories:
                df_subset = df[
                    (df[group_col] == group) & (df[stack_col] == stack_cat)
                ]

                fig.add_trace(
                    go.Bar(
                        x=df_subset[year_col].astype(str),
                        y=df_subset[value_col],
                        name=f"{group}_{stack_cat}",
                        legendgroup=stack_cat,  # Groups legend items
                        marker_color=self._color_generator.get_color(stack_cat),
                        offsetgroup=group,  # Creates separate bar groups
                        showlegend=stack_cat not in [trace.legendgroup for trace in fig.data]
                    )
                )

        fig.update_layout(
            plot_bgcolor=TRANSPARENT,
            paper_bgcolor=TRANSPARENT,
            margin_b=50,
            margin_t=20,
            margin_l=20,
            margin_r=20,
            barmode="stack",  # Stacks bars within each group
        )


        n_groups = len(years)
        n_bars = len(groups)
        fig = numbers_under_each_bar(fig, n_groups, n_bars)

        return fig



    def time_series(self, df: pd.DataFrame, group_by: str = None, chart_type: str = "Line") -> go.Figure:
        """
        Plot time series data for multiple years of a single scenario.

        Parameters
        ----------
        df : pd.DataFrame
            DataFrame with columns: scenario, year, time_period, value
            and optionally a breakdown column (sector/end_use)
        group_by : str, optional
            Column name for breakdown grouping (e.g., "sector", "end_use")
        chart_type : str, optional
            "Line" or "Area" chart type, by default "Line"

        Returns
        -------
        go.Figure
            Plotly figure with time series lines or area chart
        """
        fig = go.Figure()

        num_cols = len(df.columns)
        years = sorted(df["year"].unique())

        # Define line styles - solid for first year, dashed for subsequent years
        line_styles = ["solid", "dash", "dot", "dashdot"]

        if num_cols == 4:
            # No breakdown - plot separate lines for each year
            for i, year in enumerate(years):
                year_df = df[df["year"] == year].sort_values("time_period")

                if chart_type == "Area":
                    fig.add_trace(
                        go.Scatter(
                            x=year_df["time_period"],
                            y=year_df["value"],
                            mode="lines",
                            name=str(year),
                            line=dict(color=self._color_generator.get_color(str(year))),
                            fill='tozeroy',
                            showlegend=True
                        )
                    )
                else:  # Line chart
                    fig.add_trace(
                        go.Scatter(
                            x=year_df["time_period"],
                            y=year_df["value"],
                            mode="lines",
                            name=str(year),
                            line=dict(
                                color=self._color_generator.get_color(str(year)),
                                dash=line_styles[i % len(line_styles)]
                            ),
                            showlegend=True
                        )
                    )

        elif num_cols == 5:
            # With breakdown - plot lines for each year and sector/end_use combination
            breakdown_col = group_by if group_by else [col for col in df.columns if col not in ["scenario", "year", "time_period", "value"]][0]
            categories = sorted(df[breakdown_col].unique())

            if chart_type == "Area":
                # For area charts with breakdown, stack by category within each year
                for i, year in enumerate(years):
                    year_df = df[df["year"] == year]

                    for j, category in enumerate(categories):
                        category_df = year_df[year_df[breakdown_col] == category].sort_values("time_period")

                        if category_df.empty:
                            continue

                        # Create legend name combining year and category
                        legend_name = f"{year} - {category}" if len(years) > 1 else category

                        fig.add_trace(
                            go.Scatter(
                                x=category_df["time_period"],
                                y=category_df["value"],
                                mode="lines",
                                name=legend_name,
                                line=dict(color=self._color_generator.get_color(category)),
                                fill='tonexty' if j > 0 else 'tozeroy',
                                stackgroup=f"year_{year}",  # Separate stack group for each year
                                legendgroup=category,
                                showlegend=True
                            )
                        )
            else:  # Line chart
                for i, year in enumerate(years):
                    year_df = df[df["year"] == year]
                    line_style = line_styles[i % len(line_styles)]

                    for category in categories:
                        category_df = year_df[year_df[breakdown_col] == category].sort_values("time_period")

                        if category_df.empty:
                            continue

                        # Create legend name combining year and category
                        legend_name = f"{year} - {category}"

                        fig.add_trace(
                            go.Scatter(
                                x=category_df["time_period"],
                                y=category_df["value"],
                                mode="lines",
                                name=legend_name,
                                line=dict(
                                    color=self._color_generator.get_color(category),
                                    dash=line_style
                                ),
                                legendgroup=category,  # Group by category for better legend organization
                                showlegend=True
                            )
                        )
        else:
            # Invalid number of columns
            fig.add_annotation(
                text="Invalid data format",
                x=0.5,
                y=0.5,
                xref="paper",
                yref="paper",
                showarrow=False
            )

        fig.update_layout(
            plot_bgcolor=TRANSPARENT,
            paper_bgcolor=TRANSPARENT,
            margin=dict(l=20, r=20, t=20, b=40),
            xaxis_title="Time Period",
            yaxis_title="Energy Consumption (TWh)",
            legend=dict(
                orientation="v",
                yanchor="top",
                y=1,
                xanchor="left",
                x=1.02
            )
        )

        return fig


    def demand_curve(self, df: pd.DataFrame):
        fig = go.Figure()
        for scenario in df.columns:

            fig.add_trace(
                go.Scatter(
                    x=df.index.values,
                    y=df[scenario],
                    mode="lines",
                    marker=dict(color=self._color_generator.get_color(scenario)),
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

    def faceted_time_series(
        self,
        df: pd.DataFrame,
        chart_type: str = "Line",
        group_by: str = None,
        value_col: str = "value"
    ) -> go.Figure:
        """
        Creates faceted subplots for each scenario with shared legend.

        Parameters
        ----------
        df : pd.DataFrame
            DataFrame with columns: scenario, year, value, and optionally group_by column
        chart_type : str
            "Line" or "Area" chart type
        group_by : str, optional
            Column name to group by (e.g., "sector", "end_use")
        value_col : str
            Column name for values

        Returns
        -------
        go.Figure
            Plotly figure with subplots for each scenario
        """
        scenarios = sorted(df['scenario'].unique())
        n_scenarios = len(scenarios)

        # Calculate subplot layout (prefer horizontal layout)
        if n_scenarios <= 3:
            rows, cols = 1, n_scenarios
        elif n_scenarios <= 6:
            rows, cols = 2, 3
        else:
            rows, cols = 3, 3

        # Create subplots with scenario titles
        fig = make_subplots(
            rows=rows,
            cols=cols,
            subplot_titles=scenarios,
            shared_yaxes=True,
            vertical_spacing=0.08,
            horizontal_spacing=0.05
        )

        if group_by:
            # Get unique categories for consistent colors
            categories = sorted(df[group_by].unique())

            for i, scenario in enumerate(scenarios):
                row = (i // cols) + 1
                col = (i % cols) + 1

                scenario_df = df[df['scenario'] == scenario]

                for j, category in enumerate(categories):
                    category_df = scenario_df[scenario_df[group_by] == category]

                    if category_df.empty:
                        continue

                    # Only show legend for first subplot
                    show_legend = (i == 0)

                    if chart_type == "Area":
                        fig.add_trace(
                            go.Scatter(
                                x=category_df['year'],
                                y=category_df[value_col],
                                mode="lines",
                                name=category,
                                line=dict(color=self._color_generator.get_color(category)),
                                fill='tonexty' if j > 0 else 'tozeroy',
                                stackgroup="one",
                                showlegend=show_legend,
                                legendgroup=category
                            ),
                            row=row, col=col
                        )
                    else:  # Line chart
                        fig.add_trace(
                            go.Scatter(
                                x=category_df['year'],
                                y=category_df[value_col],
                                mode="lines+markers",
                                name=category,
                                line=dict(color=self._color_generator.get_color(category)),
                                showlegend=show_legend,
                                legendgroup=category
                            ),
                            row=row, col=col
                        )
        else:
            # No grouping - just total values per scenario
            for i, scenario in enumerate(scenarios):
                row = (i // cols) + 1
                col = (i % cols) + 1

                scenario_df = df[df['scenario'] == scenario].sort_values('year')

                if scenario_df.empty:
                    continue

                if chart_type == "Area":
                    fig.add_trace(
                        go.Scatter(
                            x=scenario_df['year'],
                            y=scenario_df[value_col],
                            mode="lines",
                            name=scenario,
                            line=dict(color=self._color_generator.get_color(scenario)),
                            fill='tozeroy',
                            showlegend=False
                        ),
                        row=row, col=col
                    )
                else:  # Line chart
                    fig.add_trace(
                        go.Scatter(
                            x=scenario_df['year'],
                            y=scenario_df[value_col],
                            mode="lines+markers",
                            name=scenario,
                            line=dict(color=self._color_generator.get_color(scenario)),
                            showlegend=False
                        ),
                        row=row, col=col
                    )

        # Update layout
        fig.update_layout(
            plot_bgcolor=TRANSPARENT,
            paper_bgcolor=TRANSPARENT,
            margin=dict(l=20, r=20, t=60, b=40),
            showlegend=group_by is not None,  # Move showlegend to main layout
            legend=dict(
                orientation="v",
                yanchor="top",
                y=1,
                xanchor="left",
                x=1.02
            ) if group_by else None,
            height=400 if rows == 1 else 600 if rows == 2 else 800
        )

        # Update x and y axes
        fig.update_xaxes(title_text="Year")
        fig.update_yaxes(title_text="Energy Consumption (TWh)", col=1)

        return fig


    def seasonal_load_lines(self, df: pd.DataFrame) -> go.Figure:
        """
        Creates faceted subplots for seasonal load lines.

        Each subplot represents a unique combination of season/day_type.
        Multiple years are plotted as separate lines within each subplot.

        Parameters
        ----------
        df : pd.DataFrame
            DataFrame from get_seasonal_load_lines with columns:
            - scenario: str
            - year: int
            - hour_of_day: int (0-23)
            - value: float
            - season: str (optional - Winter, Spring, Summer, Fall)
            - day_type: str (optional - Weekday, Weekend)

        Returns
        -------
        go.Figure
            Plotly figure with faceted subplots for each season/day_type combination
        """
        # Handle empty DataFrame
        if df.empty:
            fig = go.Figure()
            fig.add_annotation(
                text="No data available",
                x=0.5,
                y=0.5,
                xref="paper",
                yref="paper",
                showarrow=False
            )
            return fig

        # Determine grouping columns
        has_season = 'season' in df.columns
        has_day_type = 'day_type' in df.columns

        if has_season and has_day_type:
            # Both season and day_type - create 2 rows x 4 columns
            # Top row: Weekday (Winter, Spring, Summer, Fall)
            # Bottom row: Weekend (Winter, Spring, Summer, Fall)
            season_order = ['Winter', 'Spring', 'Summer', 'Fall']
            day_order = ['Weekday', 'Weekend']

            # Create ordered categories for proper subplot arrangement
            facet_categories = []
            for day_type in day_order:
                for season in season_order:
                    facet_categories.append(f"{season} - {day_type}")

            facet_col = 'season_day_type'
            df[facet_col] = df['season'] + ' - ' + df['day_type']
            df[facet_col] = pd.Categorical(df[facet_col], categories=facet_categories, ordered=True)

            rows, cols = 2, 4
            # Use subplot_titles for individual subplots
            subplot_titles = [None] * 8  # No individual subplot titles
            row_titles = ['Weekday', 'Weekend']

        elif has_season:
            # Only season - single row of 4 subplots (Winter, Spring, Summer, Fall)
            facet_col = 'season'
            season_order = ['Winter', 'Spring', 'Summer', 'Fall']
            df[facet_col] = pd.Categorical(df[facet_col], categories=season_order, ordered=True)
            facet_categories = season_order

            rows, cols = 1, 4
            subplot_titles = None  # Remove subplot titles since we'll add manual column titles
            row_titles = None

        elif has_day_type:
            # Only day_type - single row of 2 subplots (Weekday, Weekend)
            facet_col = 'day_type'
            day_order = ['Weekday', 'Weekend']
            df[facet_col] = pd.Categorical(df[facet_col], categories=day_order, ordered=True)
            facet_categories = day_order

            rows, cols = 1, 2
            subplot_titles = None  # Remove subplot titles since we'll add manual column titles
            row_titles = None

        else:
            # No grouping - single plot
            facet_col = None
            facet_categories = [None]
            rows, cols = 1, 1
            subplot_titles = None
            row_titles = None

        # Ensure cols is never 0
        if cols == 0:
            cols = 1
            rows = 1
            facet_categories = [None]
            facet_col = None
            subplot_titles = None
            row_titles = None

        if facet_col:
            # Create subplots
            fig = make_subplots(
                rows=rows,
                cols=cols,
                subplot_titles=subplot_titles,
                row_titles=row_titles,
                shared_yaxes=True,
                vertical_spacing=0.12,  # Increased spacing for row titles
                horizontal_spacing=0.05
            )
        else:
            # Single plot
            fig = go.Figure()

        # Get unique years and define line styles
        years = sorted(df['year'].unique())
        line_styles = ["solid", "dash", "dot", "dashdot"]

        # Plot data
        for i, facet_value in enumerate(facet_categories):
            if facet_col:
                row = (i // cols) + 1
                col = (i % cols) + 1
                facet_df = df[df[facet_col] == facet_value]
            else:
                row, col = 1, 1
                facet_df = df

            # Plot each year as a separate line
            for j, year in enumerate(years):
                year_df = facet_df[facet_df['year'] == year].sort_values('hour_of_day')

                if year_df.empty:
                    continue

                # Only show legend for first subplot
                show_legend = (i == 0) if facet_col else True

                if facet_col:
                    fig.add_trace(
                        go.Scatter(
                            x=year_df['hour_of_day'],
                            y=year_df['value'],
                            mode="lines",
                            name=str(year),
                            line=dict(
                                color=self._color_generator.get_color(str(year)),
                                dash=line_styles[j % len(line_styles)],
                                shape='spline'  # Enable smooth splines
                            ),
                            showlegend=show_legend,
                            legendgroup=str(year)
                        ),
                        row=row, col=col
                    )
                else:
                    fig.add_trace(
                        go.Scatter(
                            x=year_df['hour_of_day'],
                            y=year_df['value'],
                            mode="lines",
                            name=str(year),
                            line=dict(
                                color=self._color_generator.get_color(str(year)),
                                dash=line_styles[j % len(line_styles)],
                                shape='spline'  # Enable smooth splines
                            ),
                            showlegend=show_legend
                        )
                    )

        # Update layout
        if facet_col:
            # Create annotations list with existing shared axis titles
            annotations_list = [
                # Shared x-axis title
                dict(
                    text="Hour of Day",
                    xref="paper", yref="paper",
                    x=0.5, y=-0.08,
                    xanchor='center', yanchor='top',
                    font=dict(size=14),
                    showarrow=False
                ),
                # Shared y-axis title
                dict(
                    text="Load (MW)",
                    xref="paper", yref="paper",
                    x=-0.08, y=0.5,
                    xanchor='center', yanchor='middle',
                    font=dict(size=14),
                    textangle=-90,
                    showarrow=False
                )
            ]

            # Add column titles for season/day_type combination
            if has_season and has_day_type:
                season_order = ['Winter', 'Spring', 'Summer', 'Fall']
                for i, season in enumerate(season_order):
                    # Calculate x position for each column
                    x_pos = (i + 0.5) / cols
                    annotations_list.append(
                        dict(
                            text=f"<b>{season}</b>",
                            xref="paper", yref="paper",
                            x=x_pos, y=1.05,
                            xanchor='center', yanchor='bottom',
                            font=dict(size=16),
                            showarrow=False
                        )
                    )
            elif has_season:
                # Add column titles for season only
                season_order = ['Winter', 'Spring', 'Summer', 'Fall']
                for i, season in enumerate(season_order):
                    # Calculate x position for each column
                    x_pos = (i + 0.5) / cols
                    annotations_list.append(
                        dict(
                            text=f"<b>{season}</b>",
                            xref="paper", yref="paper",
                            x=x_pos, y=1.05,
                            xanchor='center', yanchor='bottom',
                            font=dict(size=16),
                            showarrow=False
                        )
                    )
            elif has_day_type:
                # Add column titles for day_type only
                day_order = ['Weekday', 'Weekend']
                for i, day_type in enumerate(day_order):
                    # Calculate x position for each column
                    x_pos = (i + 0.5) / cols
                    annotations_list.append(
                        dict(
                            text=f"<b>{day_type}</b>",
                            xref="paper", yref="paper",
                            x=x_pos, y=1.05,
                            xanchor='center', yanchor='bottom',
                            font=dict(size=16),
                            showarrow=False
                        )
                    )

            fig.update_layout(
                plot_bgcolor=TRANSPARENT,
                paper_bgcolor=TRANSPARENT,
                margin=dict(l=60, r=20, t=80, b=80),  # Increased top margin for column titles
                showlegend=True,
                legend=dict(
                    orientation="v",
                    yanchor="top",
                    y=1,
                    xanchor="left",
                    x=1.02
                ),
                height=400 if rows == 1 else 600,
                annotations=annotations_list
            )

            # Update axes with gridlines and outlines, remove individual labels
            fig.update_xaxes(
                range=[0, 23],
                showgrid=True,
                gridwidth=1,
                gridcolor='lightgray',
                tickvals=[0, 6, 12, 18, 23],
                ticktext=['0', '6', '12', '18', '23'],
                showline=True,
                linewidth=1,
                linecolor='black',
                mirror=True,  # Shows border on all sides
                title_text=""  # Remove individual titles
            )
            fig.update_yaxes(
                showline=True,
                linewidth=1,
                linecolor='black',
                mirror=True,  # Shows border on all sides
                title_text=""  # Remove individual titles
            )

            # Add vertical lines at 6, 12, and 18 for all subplots
            for row_idx in range(1, rows + 1):
                for col_idx in range(1, cols + 1):
                    for hour in [6, 12, 18]:
                        fig.add_vline(
                            x=hour,
                            line_dash="dot",
                            line_color="lightgray",
                            line_width=1,
                            row=row_idx,
                            col=col_idx
                        )
        else:
            fig.update_layout(
                plot_bgcolor=TRANSPARENT,
                paper_bgcolor=TRANSPARENT,
                margin=dict(l=20, r=20, t=20, b=40),
                xaxis_title="Hour of Day",
                yaxis_title="Load (MW)",
                xaxis=dict(
                    range=[0, 23],
                    showgrid=True,
                    gridwidth=1,
                    gridcolor='lightgray',
                    tickvals=[0, 6, 12, 18, 23],
                    ticktext=['0', '6', '12', '18', '23'],
                    showline=True,
                    linewidth=1,
                    linecolor='black',
                    mirror=True
                ),
                yaxis=dict(
                    showline=True,
                    linewidth=1,
                    linecolor='black',
                    mirror=True
                ),
                legend=dict(
                    orientation="v",
                    yanchor="top",
                    y=1,
                    xanchor="left",
                    x=1.02
                )
            )

            # Add vertical lines for single plot
            for hour in [6, 12, 18]:
                fig.add_vline(
                    x=hour,
                    line_dash="dot",
                    line_color="lightgray",
                    line_width=1
                )

        return fig

    def seasonal_load_area(self, df: pd.DataFrame) -> go.Figure:
        """
        Creates faceted area charts for seasonal load patterns with optional breakdown.

        Each subplot represents a unique combination of season/day_type.
        If breakdown is provided, areas are stacked by sector/end_use within each subplot.

        Parameters
        ----------
        df : pd.DataFrame
            DataFrame from get_seasonal_load_area with columns:
            - scenario: str
            - year: int
            - hour_of_day: int (0-23)
            - value: float
            - season: str (optional - Winter, Spring, Summer, Fall)
            - day_type: str (optional - Weekday, Weekend)
            - sector/end_use: str (optional - breakdown categories)

        Returns
        -------
        go.Figure
            Plotly figure with faceted area subplots for each season/day_type combination
        """
        # Handle empty DataFrame
        if df.empty:
            fig = go.Figure()
            fig.add_annotation(
                text="No data available",
                x=0.5,
                y=0.5,
                xref="paper",
                yref="paper",
                showarrow=False
            )
            return fig

        # Determine grouping columns
        has_season = 'season' in df.columns
        has_day_type = 'day_type' in df.columns
        has_breakdown = any(col in df.columns for col in ['sector', 'end_use'])

        # Determine breakdown column
        breakdown_col = None
        if 'sector' in df.columns:
            breakdown_col = 'sector'
        elif 'end_use' in df.columns:
            breakdown_col = 'end_use'

        if has_season and has_day_type:
            # Both season and day_type - create 2 rows x 4 columns
            season_order = ['Winter', 'Spring', 'Summer', 'Fall']
            day_order = ['Weekday', 'Weekend']

            facet_categories = []
            for day_type in day_order:
                for season in season_order:
                    facet_categories.append(f"{season} - {day_type}")

            facet_col = 'season_day_type'
            df[facet_col] = df['season'] + ' - ' + df['day_type']
            df[facet_col] = pd.Categorical(df[facet_col], categories=facet_categories, ordered=True)

            rows, cols = 2, 4
            subplot_titles = None
            row_titles = ['Weekday', 'Weekend']

        elif has_season:
            # Only season - single row of 4 subplots
            facet_col = 'season'
            season_order = ['Winter', 'Spring', 'Summer', 'Fall']
            df[facet_col] = pd.Categorical(df[facet_col], categories=season_order, ordered=True)
            facet_categories = season_order

            rows, cols = 1, 4
            subplot_titles = None
            row_titles = None

        elif has_day_type:
            # Only day_type - single row of 2 subplots
            facet_col = 'day_type'
            day_order = ['Weekday', 'Weekend']
            df[facet_col] = pd.Categorical(df[facet_col], categories=day_order, ordered=True)
            facet_categories = day_order

            rows, cols = 1, 2
            subplot_titles = None
            row_titles = None

        else:
            # No time grouping - single plot
            facet_col = None
            facet_categories = [None]
            rows, cols = 1, 1
            subplot_titles = None
            row_titles = None

        # Create subplots
        if facet_col:
            fig = make_subplots(
                rows=rows,
                cols=cols,
                subplot_titles=subplot_titles,
                row_titles=row_titles,
                shared_yaxes=True,
                vertical_spacing=0.12,
                horizontal_spacing=0.05
            )
        else:
            fig = go.Figure()

        # Get breakdown categories if available
        breakdown_categories = []
        if has_breakdown and breakdown_col:
            breakdown_categories = sorted(df[breakdown_col].unique())

        # Plot data
        for i, facet_value in enumerate(facet_categories):
            if facet_col:
                row = (i // cols) + 1
                col = (i % cols) + 1
                facet_df = df[df[facet_col] == facet_value]
            else:
                row, col = 1, 1
                facet_df = df

            if has_breakdown and breakdown_col:
                # Plot stacked areas for each breakdown category
                for j, category in enumerate(breakdown_categories):
                    category_df = facet_df[facet_df[breakdown_col] == category].sort_values('hour_of_day')

                    if category_df.empty:
                        continue

                    # Only show legend for first subplot
                    show_legend = (i == 0) if facet_col else True

                    if facet_col:
                        fig.add_trace(
                            go.Scatter(
                                x=category_df['hour_of_day'],
                                y=category_df['value'],
                                mode="lines",
                                name=category,
                                line=dict(color=self._color_generator.get_color(category)),
                                fill='tonexty' if j > 0 else 'tozeroy',
                                stackgroup=f"facet_{i}",  # Separate stack group for each facet
                                showlegend=show_legend,
                                legendgroup=category
                            ),
                            row=row, col=col
                        )
                    else:
                        fig.add_trace(
                            go.Scatter(
                                x=category_df['hour_of_day'],
                                y=category_df['value'],
                                mode="lines",
                                name=category,
                                line=dict(color=self._color_generator.get_color(category)),
                                fill='tonexty' if j > 0 else 'tozeroy',
                                stackgroup="one",
                                showlegend=show_legend
                            )
                        )
            else:
                # No breakdown - single area per facet
                facet_df = facet_df.sort_values('hour_of_day')

                if facet_df.empty:
                    continue

                if facet_col:
                    fig.add_trace(
                        go.Scatter(
                            x=facet_df['hour_of_day'],
                            y=facet_df['value'],
                            mode="lines",
                            name=str(facet_value),
                            line=dict(color=self._color_generator.get_color(str(facet_value))),
                            fill='tozeroy',
                            showlegend=False
                        ),
                        row=row, col=col
                    )
                else:
                    fig.add_trace(
                        go.Scatter(
                            x=facet_df['hour_of_day'],
                            y=facet_df['value'],
                            mode="lines",
                            name="Load",
                            line=dict(color=self._color_generator.get_color("Load")),
                            fill='tozeroy',
                            showlegend=False
                        )
                    )

        # Update layout similar to seasonal_load_lines but optimized for area charts
        if facet_col:
            # Create annotations for shared axis titles
            annotations_list = [
                dict(
                    text="Hour of Day",
                    xref="paper", yref="paper",
                    x=0.5, y=-0.08,
                    xanchor='center', yanchor='top',
                    font=dict(size=14),
                    showarrow=False
                ),
                dict(
                    text="Load (MW)",
                    xref="paper", yref="paper",
                    x=-0.08, y=0.5,
                    xanchor='center', yanchor='middle',
                    font=dict(size=14),
                    textangle=-90,
                    showarrow=False
                )
            ]

            # Add column titles based on grouping
            if has_season and has_day_type:
                season_order = ['Winter', 'Spring', 'Summer', 'Fall']
                for i, season in enumerate(season_order):
                    x_pos = (i + 0.5) / cols
                    annotations_list.append(
                        dict(
                            text=f"<b>{season}</b>",
                            xref="paper", yref="paper",
                            x=x_pos, y=1.05,
                            xanchor='center', yanchor='bottom',
                            font=dict(size=16),
                            showarrow=False
                        )
                    )
            elif has_season:
                season_order = ['Winter', 'Spring', 'Summer', 'Fall']
                for i, season in enumerate(season_order):
                    x_pos = (i + 0.5) / cols
                    annotations_list.append(
                        dict(
                            text=f"<b>{season}</b>",
                            xref="paper", yref="paper",
                            x=x_pos, y=1.05,
                            xanchor='center', yanchor='bottom',
                            font=dict(size=16),
                            showarrow=False
                        )
                    )
            elif has_day_type:
                day_order = ['Weekday', 'Weekend']
                for i, day_type in enumerate(day_order):
                    x_pos = (i + 0.5) / cols
                    annotations_list.append(
                        dict(
                            text=f"<b>{day_type}</b>",
                            xref="paper", yref="paper",
                            x=x_pos, y=1.05,
                            xanchor='center', yanchor='bottom',
                            font=dict(size=16),
                            showarrow=False
                        )
                    )

            fig.update_layout(
                plot_bgcolor=TRANSPARENT,
                paper_bgcolor=TRANSPARENT,
                margin=dict(l=60, r=20, t=80, b=80),
                showlegend=has_breakdown,
                legend=dict(
                    orientation="v",
                    yanchor="top",
                    y=1,
                    xanchor="left",
                    x=1.02
                ) if has_breakdown else None,
                height=400 if rows == 1 else 600,
                annotations=annotations_list
            )

            # Update axes
            fig.update_xaxes(
                range=[0, 23],
                showgrid=True,
                gridwidth=1,
                gridcolor='lightgray',
                tickvals=[0, 6, 12, 18, 23],
                ticktext=['0', '6', '12', '18', '23'],
                showline=True,
                linewidth=1,
                linecolor='black',
                mirror=True,
                title_text=""
            )
            fig.update_yaxes(
                showline=True,
                linewidth=1,
                linecolor='black',
                mirror=True,
                title_text=""
            )

        else:
            fig.update_layout(
                plot_bgcolor=TRANSPARENT,
                paper_bgcolor=TRANSPARENT,
                margin=dict(l=20, r=20, t=20, b=40),
                xaxis_title="Hour of Day",
                yaxis_title="Load (MW)",
                xaxis=dict(
                    range=[0, 23],
                    showgrid=True,
                    gridwidth=1,
                    gridcolor='lightgray',
                    tickvals=[0, 6, 12, 18, 23],
                    ticktext=['0', '6', '12', '18', '23'],
                    showline=True,
                    linewidth=1,
                    linecolor='black',
                    mirror=True
                ),
                yaxis=dict(
                    showline=True,
                    linewidth=1,
                    linecolor='black',
                    mirror=True
                ),
                showlegend=has_breakdown,
                legend=dict(
                    orientation="v",
                    yanchor="top",
                    y=1,
                    xanchor="left",
                    x=1.02
                ) if has_breakdown else None
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
