import pandas as pd
import numpy as np


def test_dataset_sectors():
    """
    Make a test dataset with:
     - 5 scenarios
     - 7 years range(2015, 2050, 5)
     - 17 end_uses
    """
    np.random.seed(42)
    scenarios = [f"Scenario {x}" for x in range(1, 6)]
    years = [str(x) for x in range(2015, 2050, 5)]
    end_uses = [
        "EV: Buses",
        "EV: DC Fast Charge",
        "EV: Level 1/2 Charging",
        "Pool Loads",
        "Major Appliances",
        "Refrigeration",
        "Plug and Process Loads",
        "Hot Water",
        "Lighting",
        "Fans and Pumps",
        "Heating",
        "Cooling",
        "Buildings Calibration",
        "Municipal Water",
        "Other",
        "Other Commercial",
        "Industrial",
    ]

    def empty_df(col: str, values: list[str]):
        return pd.DataFrame({col: values, "demand": 0})

    df = empty_df("scenario", scenarios).merge(
        empty_df("year", years).merge(empty_df("end_use", end_uses), on="demand"),
        on="demand",
    )

    df["demand"] = np.random.uniform(1, 100, size=df.shape[0])
    return df


def test_dataset_duration_curve(scenarios: list[str], years: list[str]):
    # for each year/scenario generate 280 draws from a normal with slightly different params
    # and then sort the draws
    # long format df

    np.random.seed(42)
    dfs = []
    for scenario in scenarios:
        for year in years:
            mu, sigma = np.random.uniform(1800, 1900), np.random.uniform(10, 20)
            demand = np.random.normal(mu, sigma, 280)
            demand.sort()
            hours = np.arange(280)
            df = pd.DataFrame(
                {
                    "scenario": scenario,
                    "year": year,
                    "demand": demand[::-1],
                    "hours": hours,
                }
            )
            dfs.append(df)

    full_df = pd.concat(dfs)
    return full_df


# if __name__ == "__main__":
#     test_dataset_sectors()
