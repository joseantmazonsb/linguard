import json
import os
from datetime import datetime, timedelta
from typing import Any

import httpx
from packaging import version as pkg_version


class VersionService:
    """Service for version management and update checking."""

    _version_cache: dict[str, Any] | None = None
    _latest_release_cache: dict[str, Any] | None = None
    _cache_timestamp: datetime | None = None
    _cache_duration = timedelta(hours=6)  # Cache for 6 hours

    def _load_version_file(self) -> dict[str, Any]:
        """Load version.json from project root."""
        version_file = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "version.json"
        )

        try:
            with open(version_file) as f:
                return json.load(f)
        except FileNotFoundError:
            # Fallback if version.json doesn't exist
            return {
                "version": "2.0.0",
                "name": "Linguard",
                "repository": "https://github.com/joseantmazonsb/linguard",
                "changelog": [],
            }

    def get_current_version(self) -> dict[str, Any]:
        """Get current version information."""
        if VersionService._version_cache is None:
            VersionService._version_cache = self._load_version_file()

        return {
            "version": VersionService._version_cache["version"],
            "name": VersionService._version_cache["name"],
            "repository": VersionService._version_cache["repository"],
        }

    async def check_for_updates(self) -> dict[str, Any]:
        """
        Check GitHub for latest release.
        Returns update information if newer version available.
        """
        # Check cache first
        now = datetime.utcnow()
        if (
            VersionService._latest_release_cache is not None
            and VersionService._cache_timestamp is not None
            and now - VersionService._cache_timestamp < VersionService._cache_duration
        ):
            return VersionService._latest_release_cache

        current_version_info = self.get_current_version()
        current_version = current_version_info["version"]

        try:
            # Get latest release from GitHub API
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://api.github.com/repos/joseantmazonsb/linguard/releases/latest",
                    timeout=10.0,
                    headers={
                        "Accept": "application/vnd.github.v3+json",
                        "User-Agent": f"LinguaRD-WebGUI/{current_version}",
                    },
                )

                if response.status_code == 404:
                    # No releases found
                    result = {
                        "current_version": current_version,
                        "update_available": False,
                        "message": "No releases found",
                    }
                elif response.status_code == 200:
                    release_data = response.json()
                    latest_version = release_data["tag_name"].lstrip("v")

                    # Compare versions
                    current = pkg_version.parse(current_version)
                    latest = pkg_version.parse(latest_version)

                    update_available = latest > current

                    result = {
                        "current_version": current_version,
                        "latest_version": latest_version,
                        "update_available": update_available,
                        "release_url": release_data["html_url"],
                        "release_notes": release_data.get("body", ""),
                        "published_at": release_data["published_at"],
                        "release_name": release_data.get("name", latest_version),
                    }
                else:
                    # API error
                    result = {
                        "current_version": current_version,
                        "update_available": False,
                        "error": f"GitHub API returned status {response.status_code}",
                    }

        except httpx.TimeoutException:
            result = {
                "current_version": current_version,
                "update_available": False,
                "error": "Timeout checking for updates",
            }
        except Exception as e:
            result = {
                "current_version": current_version,
                "update_available": False,
                "error": f"Error checking for updates: {e!s}",
            }

        # Cache the result
        VersionService._latest_release_cache = result
        VersionService._cache_timestamp = now

        return result

    def get_changelog(self) -> list:
        """Get changelog from version.json."""
        if VersionService._version_cache is None:
            VersionService._version_cache = self._load_version_file()

        return VersionService._version_cache.get("changelog", [])
