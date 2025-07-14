from pathlib import Path

import click
from chronify.loggers import setup_logging

from stride.project import Project


@click.command()
@click.argument("config_file", type=str)
@click.option(
    "-d",
    "--base-dir",
    default=Path(),
    show_default=True,
    help="Project base directory",
    callback=lambda *x: Path(x[2]),
)
@click.option(
    "--overwrite",
    default=False,
    show_default=True,
    is_flag=True,
    help="Overwrite the output directory if it exists.",
)
def deploy(config_file: Path, base_dir: Path, overwrite: bool) -> None:
    """Deploy a Stride project."""
    setup_logging(packages="dsgrid")
    project = Project.create(config_file, base_dir=base_dir, overwrite=overwrite)
    project.deploy_to_dsgrid()


if __name__ == "__main__":
    deploy()
