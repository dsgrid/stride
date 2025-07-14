from pathlib import Path

from stride.project import Project
from stride.metrics import compute_total_electricity_consumption_time_series


filename = Path("tests/data/project.json5")
project = Project.load("test_project")
name = "energy_projection"

df = compute_total_electricity_consumption_time_series(
    project.con,
    name,
    sort_by=["sector", "year", "hour"],
)
print("Total energy consumption sorted by columns")
print(df.head())
print()

df_by_sector = compute_total_electricity_consumption_time_series(
    project.con,
    name,
    pivot_dimension="sector",
)
print("Total energy consumption by sector")
print(df_by_sector.head())
