from dash import Dash, html
import dash_bootstrap_components as dbc
from pathlib import Path

from components import Components
from data_handler import DataHandler
from layouts import home_page_layout
from utils import create_color_generator
from plotting import StridePlots


assets_path = Path(__file__).parent.absolute() / "assets"
app = Dash("STRIDE", external_stylesheets=[dbc.themes.BOOTSTRAP], assets_folder=str(assets_path))

data_handler = DataHandler()

color_generator = create_color_generator(data_handler.scenarios + data_handler.end_uses)

plotter = StridePlots(color_generator)

components = Components(data_handler.scenarios, color_generator)
header = components.create_navbar()
home_page = home_page_layout(components, data_handler, plotter)

# TODO create H2 style
app.layout = [
    html.H1(children="STRIDE", style={"textAlign": "left", "padding": "5px"}),
    header,
    home_page,
]




if __name__ == "__main__":
    app.run(debug=True)
