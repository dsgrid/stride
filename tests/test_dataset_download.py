"""Tests for dataset downloading functionality."""

import os
import re
import tempfile
import zipfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner


def _strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from text."""
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


from stride.cli.stride import cli, _parse_github_url
from stride.dataset_download import (
    DatasetDownloadError,
    KnownDataset,
    _check_gh_cli_available,
    download_dataset,
    download_dataset_from_repo,
    get_default_data_directory,
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


@patch("stride.dataset_download.shutil.which")
def test_check_gh_cli_not_available(mock_which: Any) -> None:
    """Test that a clear error is raised when gh CLI is not installed."""
    mock_which.return_value = None

    with pytest.raises(DatasetDownloadError, match="GitHub CLI.*not installed"):
        _check_gh_cli_available()


@patch("stride.dataset_download.urllib.request.urlopen")
@patch("stride.dataset_download.shutil.which")
def test_download_without_gh_cli_uses_urllib(mock_which: Any, mock_urlopen: Any) -> None:
    """Test that downloading works without gh CLI by falling back to urllib."""
    import json

    # Simulate gh CLI not being available
    mock_which.return_value = None

    # Mock the GitHub API response for releases
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps([{"tag_name": "v1.0.0"}]).encode()
    mock_response.__enter__ = MagicMock(return_value=mock_response)
    mock_response.__exit__ = MagicMock(return_value=False)
    mock_urlopen.return_value = mock_response

    # This should not fail immediately due to missing gh CLI - it falls back to urllib.
    # The download proceeds (gets release version via urllib) but fails later when
    # trying to extract the invalid archive data from our mock.
    with pytest.raises(DatasetDownloadError, match="Failed to (download|extract)"):
        download_dataset_from_repo(
            repo="owner/repo",
            subdirectory="mydata",
        )


@patch("stride.dataset_download.shutil.which")
@patch("stride.dataset_download.subprocess.run")
def test_get_latest_release_tag(mock_run: Any, mock_which: Any) -> None:
    """Test getting the latest release tag."""
    mock_which.return_value = "/usr/bin/gh"  # Simulate gh CLI being installed
    mock_run.return_value = MagicMock(stdout="v1.0.0\nv0.9.0\n", returncode=0)

    tag = get_latest_release_tag("owner/repo")
    assert tag == "v1.0.0"


@patch("stride.dataset_download.shutil.which")
@patch("stride.dataset_download.subprocess.run")
def test_get_latest_release_tag_no_releases(mock_run: Any, mock_which: Any) -> None:
    """Test getting latest release when there are no releases."""
    import subprocess

    mock_which.return_value = "/usr/bin/gh"  # Simulate gh CLI being installed
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


@patch("stride.dataset_download._check_gh_cli_available")
@patch("stride.dataset_download._get_github_token")
@patch("stride.dataset_download.get_latest_release_tag")
@patch("stride.dataset_download.subprocess.run")
def test_download_dataset_from_repo(
    mock_run: Any, mock_get_tag: Any, mock_get_token: Any, mock_check_gh: Any
) -> None:
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
            data_dir=destination,
        )

        # Compare resolved paths to handle symlinks (e.g., /var -> /private/var on macOS)
        assert result.resolve() == (destination / "mydata").resolve()
        assert result.exists()
        assert (result / "data.txt").exists()
        assert (result / "config.json").exists()


@patch("stride.dataset_download._check_gh_cli_available")
@patch("stride.dataset_download._get_github_token")
@patch("stride.dataset_download.get_latest_release_tag")
@patch("stride.dataset_download.subprocess.run")
def test_download_dataset_with_test_subdirectory(
    mock_run: Any, mock_get_tag: Any, mock_get_token: Any, mock_check_gh: Any
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
            data_dir=destination,
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


@patch("stride.dataset_download._check_gh_cli_available")
@patch("stride.dataset_download._get_github_token")
@patch("stride.dataset_download.get_latest_release_tag")
@patch("stride.dataset_download.subprocess.run")
def test_download_dataset_destination_exists(
    mock_run: Any, mock_get_tag: Any, mock_get_token: Any, mock_check_gh: Any
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
                data_dir=destination,
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
    assert "Either NAME or --url must be provided" in _strip_ansi(result.output)


def test_cli_download_url_without_subdirectory() -> None:
    """Test the CLI download command with --url but no --subdirectory."""
    runner = CliRunner()
    result = runner.invoke(cli, ["datasets", "download", "--url", "https://github.com/owner/repo"])
    assert result.exit_code != 0
    assert "--subdirectory is required" in _strip_ansi(result.output)


def test_cli_list_countries() -> None:
    """Test the CLI list-countries command with the test dataset."""
    runner = CliRunner()
    result = runner.invoke(cli, ["datasets", "list-countries", "-D", "global-test"])
    assert result.exit_code == 0
    assert "country_1" in result.output
    assert "country_2" in result.output
    assert "2 total" in result.output


def test_cli_list_countries_missing_dataset() -> None:
    """Test the CLI list-countries command with a non-existent dataset."""
    runner = CliRunner()
    result = runner.invoke(cli, ["datasets", "list-countries", "-D", "nonexistent-dataset"])
    assert result.exit_code == 1
    assert "Dataset directory not found" in _strip_ansi(result.output)


def test_get_default_data_directory_default() -> None:
    """Test that get_default_data_directory returns ~/.stride/data by default."""
    # Ensure STRIDE_DATA_DIR is not set
    env_backup = os.environ.pop("STRIDE_DATA_DIR", None)
    try:
        result = get_default_data_directory()
        assert result == Path.home() / ".stride" / "data"
    finally:
        if env_backup is not None:
            os.environ["STRIDE_DATA_DIR"] = env_backup


def test_get_default_data_directory_env_var() -> None:
    """Test that get_default_data_directory respects STRIDE_DATA_DIR env var."""
    env_backup = os.environ.get("STRIDE_DATA_DIR")
    try:
        os.environ["STRIDE_DATA_DIR"] = "/custom/data/path"
        result = get_default_data_directory()
        assert result == Path("/custom/data/path")
    finally:
        if env_backup is not None:
            os.environ["STRIDE_DATA_DIR"] = env_backup
        else:
            os.environ.pop("STRIDE_DATA_DIR", None)


def test_cli_list_countries_with_data_dir() -> None:
    """Test the CLI list-countries command with --data-dir option."""
    runner = CliRunner()
    # Use the default data directory path explicitly via --data-dir
    data_dir = get_default_data_directory()
    result = runner.invoke(
        cli, ["datasets", "list-countries", "-D", "global-test", "--data-dir", str(data_dir)]
    )
    assert result.exit_code == 0
    assert "country_1" in result.output
    assert "country_2" in result.output


def test_cli_list_countries_with_invalid_data_dir() -> None:
    """Test the CLI list-countries command with invalid --data-dir."""
    runner = CliRunner()
    result = runner.invoke(
        cli, ["datasets", "list-countries", "-D", "global-test", "--data-dir", "/nonexistent/path"]
    )
    assert result.exit_code == 1
    assert "Dataset directory not found" in _strip_ansi(result.output)
