from typing import Any

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends

from ..core.containers import Container
from ..services.version_service import VersionService

router = APIRouter()


@router.get("/current", response_model=dict[str, Any])
@inject
async def get_current_version(
    version_service: VersionService = Depends(Provide[Container.version_service])
):
    """
    Get current application version.

    Returns:
        - version: Current semantic version
        - name: Application name
        - repository: GitHub repository URL
    """
    return version_service.get_current_version()


@router.get("/check-updates", response_model=dict[str, Any])
@inject
async def check_for_updates(
    version_service: VersionService = Depends(Provide[Container.version_service])
):
    """
    Check GitHub for available updates.

    Checks the GitHub repository for the latest release and compares
    with current version. Results are cached for 6 hours.

    Returns:
        - current_version: Current version
        - latest_version: Latest available version (if update available)
        - update_available: Boolean indicating if update is available
        - release_url: URL to the GitHub release page
        - release_notes: Release notes from GitHub
        - published_at: Publication date
        - release_name: Name of the release
    """
    return await version_service.check_for_updates()


@router.get("/changelog", response_model=list)
@inject
async def get_changelog(
    version_service: VersionService = Depends(Provide[Container.version_service])
):
    """
    Get application changelog.

    Returns list of version history with changes.
    """
    return version_service.get_changelog()
