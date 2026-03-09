"""System information endpoint."""

import os
import platform
import sys
import time

import psutil
from fastapi import APIRouter, Depends
from dependency_injector.wiring import Provide, inject

from ..core.containers import Container
from ..services.version_service import VersionService

router = APIRouter()

# Record startup time once at import
_START_TIME = time.time()


@router.get("")
@inject
async def system_info(
    version_service: VersionService = Depends(Provide[Container.version_service]),
):
    """Return runtime and host system information."""
    uname = platform.uname()
    version = version_service.get_current_version()
    commit = version.get("commit", "")

    uptime_seconds = int(time.time() - _START_TIME)

    mem = psutil.virtual_memory()
    cpu_percent = psutil.cpu_percent(interval=None)

    return {
        "app": {
            "name": version["name"],
            "version": version["version"],
            "python_version": sys.version,
            "git_commit": commit,
            "git_commit_short": commit[:8] if commit else "",
            "repository": version["repository"],
            "uptime_seconds": uptime_seconds,
        },
        "host": {
            "hostname": uname.node,
            "os": uname.system,
            "os_release": uname.release,
            "os_version": uname.version,
            "architecture": uname.machine,
            "cpu_count": os.cpu_count(),
            "cpu_percent": cpu_percent,
            "ram_total_bytes": mem.total,
            "ram_used_bytes": mem.used,
            "ram_available_bytes": mem.available,
            "ram_percent": mem.percent,
        },
    }
