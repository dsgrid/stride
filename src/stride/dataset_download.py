"""Download stride datasets from remote repositories."""

import os
import shutil
import subprocess
import tempfile
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path

from loguru import logger


def _get_github_token() -> str | None:
    """Get GitHub token from gh CLI if available.

    Returns
    -------
    str | None
        GitHub token or None if gh CLI is not available/authenticated
    """
    try:
        result = subprocess.run(
            ["gh", "auth", "token"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


@dataclass
class KnownDataset:
    """Configuration for a known stride dataset."""

    name: str
    repo: str
    subdirectory: str
    description: str
    test_subdirectory: str | None = None


KNOWN_DATASETS: dict[str, KnownDataset] = {
    "global": KnownDataset(
        name="global",
        repo="dsgrid/stride-data",
        subdirectory="global",
        description="Global energy projection dataset",
        test_subdirectory="global-test",
    ),
}


class DatasetDownloadError(Exception):
    """Error downloading a dataset."""


def _check_gh_cli_available() -> None:
    """Check if GitHub CLI is available and raise a clear error if not.

    Raises
    ------
    DatasetDownloadError
        If gh CLI is not installed or not in PATH
    """
    if shutil.which("gh") is None:
        msg = (
            "GitHub CLI (gh) is required but not installed or not found in PATH. "
            "Please install it from https://cli.github.com/ and ensure it's in your PATH. "
            "After installation, authenticate with 'gh auth login'."
        )
        raise DatasetDownloadError(msg)


def list_known_datasets() -> list[KnownDataset]:
    """Return the list of known downloadable datasets."""
    return list(KNOWN_DATASETS.values())


def get_release_tags(repo: str, token: str | None = None) -> list[str]:
    """Get all release tags from a GitHub repository.

    Parameters
    ----------
    repo : str
        Repository in the format "owner/repo"
    token : str | None
        GitHub token for authentication (required for private repos).
        If None, will attempt to use GitHub CLI for authentication.

    Returns
    -------
    list[str]
        List of release tag names, most recent first

    Raises
    ------
    DatasetDownloadError
        If the releases cannot be fetched
    """
    import json

    # Try using gh CLI first (handles auth automatically for private repos)
    try:
        result = subprocess.run(
            ["gh", "api", f"repos/{repo}/releases", "--jq", ".[].tag_name"],
            capture_output=True,
            text=True,
            check=True,
        )
        tags = result.stdout.strip().split("\n")
        return [tag for tag in tags if tag]  # Filter empty strings
    except subprocess.CalledProcessError as e:
        if "404" in e.stderr:
            msg = f"No releases found for repository {repo}"
            raise DatasetDownloadError(msg) from e
        msg = f"Failed to get releases for {repo}: {e.stderr}"
        raise DatasetDownloadError(msg) from e
    except FileNotFoundError:
        # gh CLI not available, fall back to direct API call
        pass

    # Fallback to direct API call (works for public repos)
    url = f"https://api.github.com/repos/{repo}/releases"
    request = urllib.request.Request(url)
    if token:
        request.add_header("Authorization", f"token {token}")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
            return [release["tag_name"] for release in data]
    except urllib.error.HTTPError as e:
        if e.code == 404:
            msg = f"Repository {repo} not found or no access"
            raise DatasetDownloadError(msg) from e
        msg = f"Failed to get releases for {repo}: {e}"
        raise DatasetDownloadError(msg) from e
    except Exception as e:
        msg = f"Failed to get releases for {repo}: {e}"
        raise DatasetDownloadError(msg) from e


def get_latest_release_tag(repo: str, token: str | None = None) -> str:
    """Get the latest release tag from a GitHub repository.

    Parameters
    ----------
    repo : str
        Repository in the format "owner/repo"
    token : str | None
        GitHub token for authentication (required for private repos)

    Returns
    -------
    str
        The tag name of the latest release (includes pre-releases)

    Raises
    ------
    DatasetDownloadError
        If the latest release cannot be determined
    """
    # Use /releases endpoint instead of /releases/latest to include pre-releases
    releases = get_release_tags(repo, token=token)
    if not releases:
        if token:
            msg = f"No releases found for repository {repo}"
        else:
            msg = (
                f"No releases found for repository {repo}. "
                "If this is a private repository, ensure GitHub CLI is installed "
                "and authenticated: run 'gh auth login'"
            )
        raise DatasetDownloadError(msg)
    return releases[0]


def download_dataset(
    name: str,
    data_dir: Path | None = None,
    version: str | None = None,
) -> Path:
    """Download a known dataset.

    Parameters
    ----------
    name : str
        Name of a known dataset (e.g., "global")
    data_dir : Path | None
        Directory where the dataset will be placed. Defaults to STRIDE_DATA_DIR
        env var or ~/.stride/data.
    version : str | None
        Release version/tag to download. Defaults to the latest release.

    Returns
    -------
    Path
        Path to the downloaded dataset directory

    Raises
    ------
    DatasetDownloadError
        If the dataset cannot be downloaded
    """
    if name not in KNOWN_DATASETS:
        available = ", ".join(KNOWN_DATASETS.keys())
        msg = f"Unknown dataset '{name}'. Available datasets: {available}"
        raise DatasetDownloadError(msg)

    dataset = KNOWN_DATASETS[name]
    return download_dataset_from_repo(
        repo=dataset.repo,
        subdirectory=dataset.subdirectory,
        data_dir=data_dir,
        version=version,
        test_subdirectory=dataset.test_subdirectory,
    )


def get_default_data_directory() -> Path:
    """Get the default directory for storing downloaded datasets.

    Checks the STRIDE_DATA_DIR environment variable first, falling back
    to ~/.stride/data if not set.

    Returns
    -------
    Path
        Default data directory (STRIDE_DATA_DIR or ~/.stride/data)
    """
    env_dir = os.getenv("STRIDE_DATA_DIR")
    if env_dir:
        return Path(env_dir)
    return Path.home() / ".stride" / "data"


def _download_archive_with_gh(repo: str, version: str, archive_path: Path) -> None:
    """Download release archive using GitHub CLI.

    Parameters
    ----------
    repo : str
        Repository in the format "owner/repo"
    version : str
        Release version/tag to download
    archive_path : Path
        Path where the archive will be saved

    Raises
    ------
    DatasetDownloadError
        If the download fails
    FileNotFoundError
        If gh CLI is not available
    """
    result = subprocess.run(
        [
            "gh",
            "release",
            "download",
            version,
            "--repo",
            repo,
            "--archive",
            "zip",
            "--output",
            str(archive_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        # Check if the error is due to an outdated gh CLI version
        if "unknown flag: --output" in result.stderr:
            msg = (
                "Your GitHub CLI version does not support the '--output' flag. "
                "Please update GitHub CLI to the latest version. "
                "Visit https://github.com/cli/cli/releases for installation instructions, "
                "or run 'gh upgrade' if supported by your installation method."
            )
        else:
            msg = f"GitHub CLI download failed: {result.stderr.strip()}"
        raise DatasetDownloadError(msg)


def _download_archive_with_urllib(archive_url: str, archive_path: Path, token: str | None) -> None:
    """Download archive using urllib (fallback method).

    Parameters
    ----------
    archive_url : str
        URL to download the archive from
    archive_path : Path
        Path where the archive will be saved
    token : str | None
        GitHub token for authentication

    Raises
    ------
    DatasetDownloadError
        If the download fails
    """
    try:
        request = urllib.request.Request(archive_url)
        if token:
            request.add_header("Authorization", f"token {token}")
        with urllib.request.urlopen(request, timeout=300) as response:
            with open(archive_path, "wb") as f:
                f.write(response.read())
    except Exception as e:
        msg = f"Failed to download archive from {archive_url}: {e}"
        raise DatasetDownloadError(msg) from e


def _download_archive(repo: str, version: str, archive_path: Path, token: str | None) -> None:
    """Download release archive using GitHub CLI.

    Parameters
    ----------
    repo : str
        Repository in the format "owner/repo"
    version : str
        Release version/tag to download
    archive_path : Path
        Path where the archive will be saved
    token : str | None
        GitHub token for authentication (not used, kept for compatibility)

    Raises
    ------
    DatasetDownloadError
        If the download fails
    """
    archive_url = f"https://github.com/{repo}/archive/refs/tags/{version}.zip"
    logger.info("Downloading from {}", archive_url)

    try:
        _download_archive_with_gh(repo, version, archive_path)
    except FileNotFoundError as e:
        msg = (
            "GitHub CLI (gh) is not installed or not found in PATH. "
            "Please install it from https://cli.github.com/ and ensure it's in your PATH. "
            "After installation, authenticate with 'gh auth login'."
        )
        raise DatasetDownloadError(msg) from e

    logger.info("Downloaded archive to {}", archive_path)


def _extract_archive(archive_path: Path, extract_path: Path) -> None:
    """Extract a zip archive.

    Parameters
    ----------
    archive_path : Path
        Path to the zip archive
    extract_path : Path
        Directory to extract the archive into

    Raises
    ------
    DatasetDownloadError
        If extraction fails
    """
    try:
        with zipfile.ZipFile(archive_path, "r") as zip_ref:
            zip_ref.extractall(extract_path)
    except Exception as e:
        msg = f"Failed to extract archive: {e}"
        raise DatasetDownloadError(msg) from e

    logger.info("Extracted archive to {}", extract_path)


def _find_source_in_archive(extract_path: Path, subdirectory: str) -> Path:
    """Find the source directory within an extracted GitHub archive.

    Parameters
    ----------
    extract_path : Path
        Path where the archive was extracted
    subdirectory : str
        Subdirectory to find within the archive

    Returns
    -------
    Path
        Path to the source directory

    Raises
    ------
    DatasetDownloadError
        If the subdirectory cannot be found
    """
    # GitHub adds repo-name-tag prefix to extracted directory
    extracted_dirs = list(extract_path.iterdir())
    if len(extracted_dirs) != 1:
        msg = f"Expected one directory in archive, found {len(extracted_dirs)}"
        raise DatasetDownloadError(msg)

    repo_root = extracted_dirs[0]
    source_path = repo_root / subdirectory

    if not source_path.exists():
        msg = f"Subdirectory '{subdirectory}' not found in archive"
        raise DatasetDownloadError(msg)

    return source_path


def _move_to_destination(source_path: Path, destination: Path, subdirectory: str) -> Path:
    """Move extracted dataset to final destination.

    Parameters
    ----------
    source_path : Path
        Path to the source directory to move
    destination : Path
        Base destination directory
    subdirectory : str
        Subdirectory name for the final location

    Returns
    -------
    Path
        Path to the final destination

    Raises
    ------
    DatasetDownloadError
        If the destination already exists
    """
    final_destination = destination / subdirectory
    if final_destination.exists():
        msg = f"Destination already exists: {final_destination}"
        raise DatasetDownloadError(msg)

    destination.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source_path), str(final_destination))
    logger.info("Moved dataset to {}", final_destination)

    return final_destination


def download_dataset_from_repo(
    repo: str,
    subdirectory: str,
    data_dir: Path | None = None,
    version: str | None = None,
    test_subdirectory: str | None = None,
) -> Path:
    """Download a dataset from a GitHub repository.

    Parameters
    ----------
    repo : str
        Repository in the format "owner/repo"
    subdirectory : str
        Subdirectory within the repository containing the dataset
    data_dir : Path | None
        Directory where the dataset will be placed. Defaults to STRIDE_DATA_DIR
        env var or ~/.stride/data.
    version : str | None
        Release version/tag to download. Defaults to the latest release.
    test_subdirectory : str | None
        Optional subdirectory containing test data. If provided, both the main
        dataset and test dataset will be extracted from the same archive.

    Returns
    -------
    Path
        Path to the downloaded dataset directory

    Raises
    ------
    DatasetDownloadError
        If the dataset cannot be downloaded
    """
    # Check upfront that gh CLI is available (required for downloading)
    _check_gh_cli_available()

    data_dir = data_dir or get_default_data_directory()
    data_dir = data_dir.resolve()

    # Get GitHub token for private repo access
    token = _get_github_token()
    if token:
        logger.debug("Using GitHub CLI token for authentication")
    else:
        logger.debug("No GitHub token found; private repositories will not be accessible")

    if version is None:
        version = get_latest_release_tag(repo, token=token)
        logger.info("Using latest release: {}", version)

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        archive_path = tmp_path / "archive.zip"
        extract_path = tmp_path / "extracted"

        _download_archive(repo, version, archive_path, token)
        _extract_archive(archive_path, extract_path)

        # Extract main dataset
        source_path = _find_source_in_archive(extract_path, subdirectory)
        result = _move_to_destination(source_path, data_dir, subdirectory)

        # Extract test dataset if specified
        if test_subdirectory:
            test_source_path = _find_source_in_archive(extract_path, test_subdirectory)
            _move_to_destination(test_source_path, data_dir, test_subdirectory)
            logger.info("Also extracted test dataset: {}", test_subdirectory)

        return result
