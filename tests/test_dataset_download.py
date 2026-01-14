"""Tests for dataset downloading functionality."""

import tempfile
import zipfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from stride.cli.stride import cli, _parse_github_url
from stride.dataset_download import (
    DatasetDownloadError,
    KnownDataset,
    download_dataset,
    download_dataset_from_repo,
    get_latest_release_tag,
    list_known_datasets,
    KNOWN_DATASETS,
)


def test_list_known_datasets() -> None:
    """Test that list_known_datasets returns the expected datasets."""
    datasets = list_known_datasets()
    assert len(datasets) >= 1
    names = {d.name for d in datasets}
    assert "global" in names


def test_known_datasets_have_required_fields() -> None:
    """Test that all known datasets have required fields."""
    for name, dataset in KNOWN_DATASETS.items():
        assert isinstance(dataset, KnownDataset)
        assert dataset.name == name
        assert dataset.repo
        assert dataset.subdirectory
        assert dataset.description


def test_global_dataset_has_test_subdirectory() -> None:
    """Test that the global dataset has an associated test dataset."""
    global_dataset = KNOWN_DATASETS["global"]
    assert global_dataset.test_subdirectory == "global-test"


def test_parse_github_url_valid() -> None:
    """Test parsing valid GitHub URLs."""
    assert _parse_github_url("https://github.com/owner/repo") == "owner/repo"
    assert _parse_github_url("https://github.com/owner/repo/") == "owner/repo"
    assert _parse_github_url("https://github.com/owner/repo.git") == "owner/repo"
    assert _parse_github_url("github.com/owner/repo") == "owner/repo"


def test_parse_github_url_invalid() -> None:
    """Test parsing invalid GitHub URLs."""
    from click import UsageError

    with pytest.raises(UsageError):
        _parse_github_url("https://gitlab.com/owner/repo")

    with pytest.raises(UsageError):
        _parse_github_url("not a url")


def test_download_unknown_dataset() -> None:
    """Test that downloading an unknown dataset raises an error."""
    with pytest.raises(DatasetDownloadError, match="Unknown dataset"):
        download_dataset("nonexistent_dataset")


@patch("stride.dataset_download.subprocess.run")
def test_get_latest_release_tag(mock_run: Any) -> None:
    """Test getting the latest release tag."""
    mock_run.return_value = MagicMock(stdout="v1.0.0\nv0.9.0\n", returncode=0)

    tag = get_latest_release_tag("owner/repo")
    assert tag == "v1.0.0"


@patch("stride.dataset_download.subprocess.run")
def test_get_latest_release_tag_no_releases(mock_run: Any) -> None:
    """Test getting latest release when there are no releases."""
    import subprocess

    mock_run.side_effect = subprocess.CalledProcessError(returncode=1, cmd="gh", stderr="404")

    with pytest.raises(DatasetDownloadError, match="No releases found"):
        get_latest_release_tag("owner/repo")


def create_test_archive(
    archive_path: Path, repo_name: str, subdirectory: str, test_subdirectory: str | None = None
) -> None:
    """Create a test zip archive with a subdirectory and optional test subdirectory."""
    with zipfile.ZipFile(archive_path, "w") as zf:
        # Create the expected directory structure
        prefix = f"{repo_name}-v1.0.0"
        zf.writestr(f"{prefix}/{subdirectory}/data.txt", "test data content")
        zf.writestr(f"{prefix}/{subdirectory}/config.json", '{"key": "value"}')
        if test_subdirectory:
            zf.writestr(f"{prefix}/{test_subdirectory}/test_data.txt", "test dataset content")
            zf.writestr(f"{prefix}/{test_subdirectory}/test_config.json", '{"test": true}')


@patch("stride.dataset_download._get_github_token")
@patch("stride.dataset_download.get_latest_release_tag")
@patch("stride.dataset_download.subprocess.run")
def test_download_dataset_from_repo(mock_run: Any, mock_get_tag: Any, mock_get_token: Any) -> None:
    """Test downloading a dataset from a repository."""
    mock_get_tag.return_value = "v1.0.0"
    mock_get_token.return_value = None

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        destination = tmp_path / "dest"
        destination.mkdir()

        # Create a fake archive that will be "downloaded"
        source_archive = tmp_path / "source_archive.zip"
        create_test_archive(source_archive, "repo", "mydata")

        # Mock subprocess.run to copy our test archive to the output path
        def fake_run(cmd: list[str], **kwargs: Any) -> MagicMock:
            import shutil

            if "gh" in cmd and "release" in cmd and "download" in cmd:
                # Find the --output argument
                output_idx = cmd.index("--output") + 1
                output_path = cmd[output_idx]
                shutil.copy(source_archive, output_path)
                return MagicMock(returncode=0)
            return MagicMock(returncode=0)

        mock_run.side_effect = fake_run

        result = download_dataset_from_repo(
            repo="owner/repo",
            subdirectory="mydata",
            destination=destination,
        )

        # Compare resolved paths to handle symlinks (e.g., /var -> /private/var on macOS)
        assert result.resolve() == (destination / "mydata").resolve()
        assert result.exists()
        assert (result / "data.txt").exists()
        assert (result / "config.json").exists()


@patch("stride.dataset_download._get_github_token")
@patch("stride.dataset_download.get_latest_release_tag")
@patch("stride.dataset_download.subprocess.run")
def test_download_dataset_with_test_subdirectory(
    mock_run: Any, mock_get_tag: Any, mock_get_token: Any
) -> None:
    """Test downloading a dataset with its test subdirectory."""
    mock_get_tag.return_value = "v1.0.0"
    mock_get_token.return_value = None

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        destination = tmp_path / "dest"
        destination.mkdir()

        # Create a fake archive with both main and test data
        source_archive = tmp_path / "source_archive.zip"
        create_test_archive(source_archive, "repo", "mydata", test_subdirectory="mydata-test")

        def fake_run(cmd: list[str], **kwargs: Any) -> MagicMock:
            import shutil

            if "gh" in cmd and "release" in cmd and "download" in cmd:
                output_idx = cmd.index("--output") + 1
                output_path = cmd[output_idx]
                shutil.copy(source_archive, output_path)
                return MagicMock(returncode=0)
            return MagicMock(returncode=0)

        mock_run.side_effect = fake_run

        result = download_dataset_from_repo(
            repo="owner/repo",
            subdirectory="mydata",
            destination=destination,
            test_subdirectory="mydata-test",
        )

        # Main dataset should be downloaded
        assert result.resolve() == (destination / "mydata").resolve()
        assert result.exists()
        assert (result / "data.txt").exists()
        assert (result / "config.json").exists()

        # Test dataset should also be downloaded
        test_path = destination / "mydata-test"
        assert test_path.exists()
        assert (test_path / "test_data.txt").exists()
        assert (test_path / "test_config.json").exists()


@patch("stride.dataset_download._get_github_token")
@patch("stride.dataset_download.get_latest_release_tag")
@patch("stride.dataset_download.subprocess.run")
def test_download_dataset_destination_exists(
    mock_run: Any, mock_get_tag: Any, mock_get_token: Any
) -> None:
    """Test that downloading fails if destination already exists."""
    mock_get_tag.return_value = "v1.0.0"
    mock_get_token.return_value = None

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        destination = tmp_path / "dest"
        destination.mkdir()

        # Create existing destination
        existing = destination / "mydata"
        existing.mkdir()

        # Create a fake archive
        source_archive = tmp_path / "source_archive.zip"
        create_test_archive(source_archive, "repo", "mydata")

        def fake_run(cmd: list[str], **kwargs: Any) -> MagicMock:
            import shutil

            if "gh" in cmd and "release" in cmd and "download" in cmd:
                output_idx = cmd.index("--output") + 1
                output_path = cmd[output_idx]
                shutil.copy(source_archive, output_path)
                return MagicMock(returncode=0)
            return MagicMock(returncode=0)

        mock_run.side_effect = fake_run

        with pytest.raises(DatasetDownloadError, match="Destination already exists"):
            download_dataset_from_repo(
                repo="owner/repo",
                subdirectory="mydata",
                destination=destination,
            )


def test_cli_list_remote() -> None:
    """Test the CLI list-remote command."""
    runner = CliRunner()
    result = runner.invoke(cli, ["datasets", "list-remote"])
    assert result.exit_code == 0
    assert "global" in result.output
    # global-test is no longer a separate dataset; it's downloaded with global
    assert "test_subdirectory: global-test" in result.output


def test_cli_download_no_args() -> None:
    """Test the CLI download command with no arguments."""
    runner = CliRunner()
    result = runner.invoke(cli, ["datasets", "download"])
    assert result.exit_code != 0
    assert "Either NAME or --url must be provided" in result.output


def test_cli_download_url_without_subdirectory() -> None:
    """Test the CLI download command with --url but no --subdirectory."""
    runner = CliRunner()
    result = runner.invoke(cli, ["datasets", "download", "--url", "https://github.com/owner/repo"])
    assert result.exit_code != 0
    assert "--subdirectory is required" in result.output
