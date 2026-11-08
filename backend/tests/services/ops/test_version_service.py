"""Tests for VersionService: version file loading, update checking and caching."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

import app.services.version_service as version_module
from app.services.version_service import VersionService

RELEASE_URL = "https://api.github.com/repos/joseantmazonsb/linguard/releases/latest"


@pytest.fixture(autouse=True)
def reset_caches():
    """VersionService caches live on the class, so reset them for every test."""
    VersionService._version_cache = None
    VersionService._latest_release_cache = None
    VersionService._cache_timestamp = None
    yield
    VersionService._version_cache = None
    VersionService._latest_release_cache = None
    VersionService._cache_timestamp = None


@pytest.fixture
def service():
    return VersionService()


class FakeResponse:
    def __init__(self, status_code=200, json_data=None, text=""):
        self.status_code = status_code
        self._json = json_data
        self.text = text

    def json(self):
        if self._json is None:
            raise ValueError("no json")
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=MagicMock(), response=self)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False


def _fake_client(get_result):
    """Build a patched httpx.AsyncClient whose GET returns `get_result`."""
    client = MagicMock()
    if isinstance(get_result, Exception):
        client.get = AsyncMock(side_effect=get_result)
    else:
        client.get = AsyncMock(return_value=get_result)
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=client)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm, client


def test_should_load_version_json_from_project_root_when_file_exists(service):
    info = service.get_current_version()

    assert info["name"] == "Linguard"
    assert info["repository"].startswith("https://github.com/")
    assert info["version"]
    # commit is present in the repo's version.json
    assert "commit" in info


def test_should_return_fallback_version_when_version_file_missing(service):
    with patch("builtins.open", side_effect=FileNotFoundError):
        loaded = service._load_version_file()

    assert loaded == {
        "version": "2.0.0",
        "name": "Linguard",
        "repository": "https://github.com/joseantmazonsb/linguard",
        "changelog": [],
    }


def test_should_cache_version_file_when_loaded_twice(service):
    with patch.object(VersionService, "_load_version_file", return_value={
        "version": "9.9.9", "name": "Cached", "repository": "r", "changelog": []
    }) as load:
        first = service.get_current_version()
        second = service.get_current_version()

    assert load.call_count == 1
    assert first["version"] == "9.9.9"
    assert second == first


def test_should_return_empty_commit_when_version_file_has_no_commit():
    VersionService._version_cache = {"version": "1.0.0", "name": "Ling", "repository": "repo"}

    info = VersionService().get_current_version()

    assert info["commit"] == ""


async def test_should_report_update_available_when_github_release_is_newer(service):
    VersionService._version_cache = {
        "version": "1.0.0", "name": "Linguard", "repository": "repo", "changelog": []
    }
    release = {
        "tag_name": "v2.5.0",
        "html_url": "https://github.com/releases/2.5.0",
        "body": "Release notes",
        "published_at": "2026-01-01T00:00:00Z",
        "name": "Version 2.5.0",
    }
    cm, client = _fake_client(FakeResponse(200, release))

    with patch.object(version_module.httpx, "AsyncClient", return_value=cm):
        result = await service.check_for_updates()

    assert result["update_available"] is True
    assert result["latest_version"] == "2.5.0"
    assert result["current_version"] == "1.0.0"
    assert result["release_url"] == "https://github.com/releases/2.5.0"
    assert result["release_notes"] == "Release notes"
    assert result["release_name"] == "Version 2.5.0"
    assert result["published_at"] == "2026-01-01T00:00:00Z"


async def test_should_report_no_update_when_github_release_is_older(service):
    VersionService._version_cache = {
        "version": "2.0.0", "name": "Linguard", "repository": "repo", "changelog": []
    }
    release = {"tag_name": "v1.9.0", "html_url": "u", "published_at": "2025-01-01T00:00:00Z"}
    cm, _ = _fake_client(FakeResponse(200, release))

    with patch.object(version_module.httpx, "AsyncClient", return_value=cm):
        result = await service.check_for_updates()

    assert result["update_available"] is False
    # release_name falls back to the latest version when GitHub omits "name"
    assert result["release_name"] == "1.9.0"


async def test_should_report_no_update_when_github_returns_404(service):
    cm, _ = _fake_client(FakeResponse(404, None))

    with patch.object(version_module.httpx, "AsyncClient", return_value=cm):
        result = await service.check_for_updates()

    assert result["update_available"] is False
    assert result["message"] == "No releases found"


async def test_should_return_error_when_github_returns_server_error(service):
    cm, _ = _fake_client(FakeResponse(500, None))

    with patch.object(version_module.httpx, "AsyncClient", return_value=cm):
        result = await service.check_for_updates()

    assert result["update_available"] is False
    assert "500" in result["error"]


async def test_should_return_error_when_github_request_times_out(service):
    cm, _ = _fake_client(httpx.TimeoutException("timed out"))

    with patch.object(version_module.httpx, "AsyncClient", return_value=cm):
        result = await service.check_for_updates()

    assert result["update_available"] is False
    assert result["error"] == "Timeout checking for updates"


async def test_should_return_error_when_unexpected_failure_occurs(service):
    cm, _ = _fake_client(httpx.ConnectError("boom"))

    with patch.object(version_module.httpx, "AsyncClient", return_value=cm):
        result = await service.check_for_updates()

    assert result["update_available"] is False
    assert "boom" in result["error"]


async def test_should_reuse_cached_release_when_cache_is_fresh(service):
    VersionService._latest_release_cache = {"cached": True}
    VersionService._cache_timestamp = datetime.utcnow() - timedelta(hours=1)

    cm, client = _fake_client(FakeResponse(200, {}))
    with patch.object(version_module.httpx, "AsyncClient", return_value=cm):
        result = await service.check_for_updates()

    assert result == {"cached": True}
    client.get.assert_not_awaited()


async def test_should_refetch_when_cached_release_is_stale(service):
    VersionService._latest_release_cache = {"cached": True}
    VersionService._cache_timestamp = datetime.utcnow() - timedelta(hours=7)

    release = {"tag_name": "v9.0.0", "html_url": "u", "published_at": "p"}
    cm, client = _fake_client(FakeResponse(200, release))
    with patch.object(version_module.httpx, "AsyncClient", return_value=cm):
        result = await service.check_for_updates()

    assert result["latest_version"] == "9.0.0"
    client.get.assert_awaited_once()
    # The fresh result replaces the cache
    assert VersionService._latest_release_cache == result
    assert VersionService._cache_timestamp is not None


def test_should_return_changelog_when_version_file_has_one(service):
    changelog = service.get_changelog()

    assert isinstance(changelog, list)
    assert changelog and "version" in changelog[0]


def test_should_return_empty_changelog_when_version_file_has_none():
    VersionService._version_cache = {"version": "1.0.0", "name": "L", "repository": "r"}

    assert VersionService().get_changelog() == []
