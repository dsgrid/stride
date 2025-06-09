import numpy as np
import pandas as pd
from functools import cached_property

from tests.data import test_dataset_sectors, test_dataset_duration_curve


class DataHandler:

    def __init__(self):
        self._sector_df = test_dataset_sectors()
        self._scenarios = list(self._sector_df["scenario"].unique())
        self._end_uses = list(self._sector_df["end_use"].unique())
        self._years = list(self._sector_df["year"].unique())

        self._duration_df = test_dataset_duration_curve(self._scenarios, self._years)

    @cached_property
    def scenarios(self) -> list[str]:
        return list(self._sector_df["scenario"].unique())

    @cached_property
    def end_uses(self) -> list[str]:
        return list(self._sector_df["end_use"].unique())

    @cached_property
    def years(self) -> list[str]:
        return list(self._sector_df["year"].unique())

    def sector_df(
        self,
        scenarios: list[str] | None = None,
        end_uses: list[str] | None = None,
    ) -> pd.DataFrame:
        filters = []
        if scenarios is not None:
            filters.append(self._sector_df["scenario"].isin(scenarios))
        if end_uses is not None:
            filters.append(self._sector_df["end_use"].isin(end_uses))

        filter = np.logical_and.reduce(filters)
        return self._sector_df[filter]  # type: ignore

    def duration_df(
        self,
        scenarios: list[str] | None = None,
        years: list[str] | None = None,
    ) -> pd.DataFrame:
        filters = []
        if scenarios is not None:
            filters.append(self._duration_df["scenario"].isin(scenarios))
        if years is not None:
            filters.append(self._duration_df["year"].isin(years))

        filter = np.logical_and.reduce(filters)
        return self._duration_df[filter]  # type: ignore
