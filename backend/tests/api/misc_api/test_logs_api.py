"""Tests for ``app/api/logs.py``.

The log file lives in ``tmp_path`` and ``log_path`` is pointed at it, so the
info/download endpoints read a real file. The SSE stream itself is infinite by
design, so its generator is exercised directly (and the HTTP endpoint only for
the authentication branches that fail before streaming starts).
"""

import os

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import select

from app.api.logs import (
    admin_from_query_token,
    format_bytes,
    get_log_file_path,
    stream_logs,
    tail_log_file,
)
from app.models.settings import GlobalSettings

BASE = "/api/v1/logs"

LOG_TEXT = "line one\nline two\nline three\n"


def _token(headers):
    return headers["Authorization"].split(" ", 1)[1]


@pytest_asyncio.fixture
async def log_file(tmp_path, seeded_db, db_session):
    """A real log file plus the matching ``log_path`` setting."""
    path = tmp_path / "logs" / "linguard.log"
    path.parent.mkdir()
    path.write_text(LOG_TEXT)
    settings = (await db_session.execute(select(GlobalSettings))).scalar_one()
    settings.log_path = str(path)
    await db_session.commit()
    return path


async def _set_log_path(db_session, value):
    settings = (await db_session.execute(select(GlobalSettings))).scalar_one()
    settings.log_path = value
    await db_session.commit()
    return settings


# ---------------------------------------------------------------------------
# /info
# ---------------------------------------------------------------------------

async def test_should_return_log_info_when_file_exists(auth_client, log_file):
    response = auth_client.get(BASE + "/info")

    assert response.status_code == 200
    body = response.json()
    assert body["path"] == str(log_file)
    assert body["size_bytes"] == len(LOG_TEXT)
    assert body["size_human"].endswith("B")
    assert body["line_count"] == 3
    assert body["last_modified"] == pytest.approx(os.path.getmtime(log_file))


async def test_should_return_404_when_log_file_is_missing(auth_client, log_file):
    log_file.unlink()

    response = auth_client.get(BASE + "/info")

    assert response.status_code == 404
    assert response.json()["detail"] == "Log file not found"


async def test_should_return_404_when_log_path_is_not_configured(
    auth_client, log_file, db_session
):
    await _set_log_path(db_session, "")

    response = auth_client.get(BASE + "/info")

    assert response.status_code == 404
    assert "not configured" in response.json()["detail"]


async def test_should_reject_log_info_when_user_is_not_admin(user_client, log_file):
    response = user_client.get(BASE + "/info")

    assert response.status_code == 403


async def test_should_require_authentication_when_reading_log_info(api_client, seeded_db):
    assert api_client.get(BASE + "/info").status_code == 401


async def test_should_resolve_relative_log_path_when_configuring_logs(
    auth_client, db_session, tmp_path, monkeypatch
):
    (tmp_path / "relative.log").write_text("hello\n")
    await _set_log_path(db_session, "relative.log")
    monkeypatch.chdir(tmp_path)

    response = auth_client.get(BASE + "/info")

    assert response.status_code == 200
    assert response.json()["path"] == str(tmp_path / "relative.log")


# ---------------------------------------------------------------------------
# /download (query-token authentication)
# ---------------------------------------------------------------------------

async def test_should_download_log_file_when_token_is_valid(api_client, seeded_db, log_file, admin_headers):
    response = api_client.get(BASE + "/download", params={"token": _token(admin_headers)})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert "linguard.log" in response.headers["content-disposition"]
    assert response.text == LOG_TEXT


async def test_should_accept_any_token_when_auth_is_disabled(
    api_client, seeded_db, db_session, log_file
):
    settings = (await db_session.execute(select(GlobalSettings))).scalar_one()
    settings.disable_auth = True
    await db_session.commit()

    response = api_client.get(BASE + "/download", params={"token": "not-a-jwt"})

    assert response.status_code == 200
    assert response.text == LOG_TEXT


async def test_should_reject_download_when_token_is_missing(api_client, seeded_db, log_file):
    response = api_client.get(BASE + "/download")

    assert response.status_code == 401
    assert response.json()["detail"] == "Authentication token required"


async def test_should_reject_download_when_token_is_invalid(api_client, seeded_db, log_file):
    response = api_client.get(BASE + "/download", params={"token": "garbage"})

    assert response.status_code == 401
    assert response.json()["detail"] == "Could not validate credentials"


async def test_should_reject_download_when_token_user_is_unknown(
    api_client, seeded_db, log_file
):
    from datetime import datetime, timedelta

    from jose import jwt

    from tests.conftest import TEST_SECRET_KEY

    token = jwt.encode(
        {"sub": "ghost", "exp": datetime.utcnow() + timedelta(minutes=5)},
        TEST_SECRET_KEY,
        algorithm="HS256",
    )

    response = api_client.get(BASE + "/download", params={"token": token})

    assert response.status_code == 401
    assert response.json()["detail"] == "Could not validate credentials"


async def test_should_reject_download_when_token_has_no_subject(
    api_client, seeded_db, log_file
):
    from datetime import datetime, timedelta

    from jose import jwt

    from tests.conftest import TEST_SECRET_KEY

    token = jwt.encode(
        {"exp": datetime.utcnow() + timedelta(minutes=5)},
        TEST_SECRET_KEY,
        algorithm="HS256",
    )

    response = api_client.get(BASE + "/download", params={"token": token})

    assert response.status_code == 401
    assert response.json()["detail"] == "Could not validate credentials"


async def test_should_reject_download_when_user_is_not_admin(
    api_client, seeded_db, log_file, user_headers
):
    response = api_client.get(BASE + "/download", params={"token": _token(user_headers)})

    assert response.status_code == 403
    assert response.json()["detail"] == "Administrator privileges required"


async def test_should_return_404_when_downloading_missing_log_file(
    api_client, seeded_db, log_file, admin_headers
):
    log_file.unlink()

    response = api_client.get(BASE + "/download", params={"token": _token(admin_headers)})

    assert response.status_code == 404
    assert response.json()["detail"] == "Log file not found"


# ---------------------------------------------------------------------------
# /stream authentication (never consume the infinite stream)
# ---------------------------------------------------------------------------

async def test_should_reject_stream_when_token_is_missing(api_client, seeded_db):
    response = api_client.get(BASE + "/stream")

    assert response.status_code == 401


async def test_should_reject_stream_when_user_is_not_admin(
    api_client, seeded_db, user_headers
):
    response = api_client.get(BASE + "/stream", params={"token": _token(user_headers)})

    assert response.status_code == 403


async def test_should_build_event_stream_response_when_called(seeded_db, db_session, log_file):
    settings = (await db_session.execute(select(GlobalSettings))).scalar_one()

    response = await stream_logs(lines=10, log_path=str(log_file), current_user=None)

    assert response.media_type == "text/event-stream"
    assert response.headers["cache-control"] == "no-cache"
    assert response.headers["x-accel-buffering"] == "no"
    await response.body_iterator.aclose()
    assert settings.log_path == str(log_file)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def test_should_report_missing_file_when_tailing_log_file(log_file, tmp_path):
    missing = tmp_path / "nope.log"

    generator = tail_log_file(str(missing))
    chunk = await anext(generator)
    with pytest.raises(StopAsyncIteration):
        await anext(generator)
    await generator.aclose()

    assert chunk == f"data: Log file not found: {missing}\n\n"


async def test_should_stream_last_lines_when_tailing_log_file(log_file):
    generator = tail_log_file(str(log_file), lines=2)

    first = await anext(generator)
    second = await anext(generator)
    await generator.aclose()

    assert first == "data: line two\n\n"
    assert second == "data: line three\n\n"


async def test_should_stream_lines_appended_after_tailing_started(log_file):
    """The tail keeps reading the file after the initial snapshot."""
    import asyncio

    generator = tail_log_file(str(log_file), lines=1)
    assert await anext(generator) == "data: line three\n\n"

    pending = asyncio.create_task(anext(generator))

    # Give the generator time to open the file and position itself at the end.
    await asyncio.sleep(0.1)
    with open(log_file, "a") as handle:
        handle.write("brand new line\n")

    try:
        chunk = await asyncio.wait_for(pending, timeout=10)
    finally:
        pending.cancel()
        await generator.aclose()

    assert chunk == "data: brand new line\n\n"


async def test_should_report_error_when_log_path_is_a_directory(tmp_path):
    directory = tmp_path / "logs-dir"
    directory.mkdir()

    generator = tail_log_file(str(directory))
    chunk = await anext(generator)
    await generator.aclose()

    assert chunk.startswith("data: Error reading log file:")


async def test_should_return_500_when_log_info_cannot_be_read(
    auth_client, log_file, db_session, tmp_path
):
    directory = tmp_path / "logs-dir"
    directory.mkdir()
    await _set_log_path(db_session, str(directory))

    response = auth_client.get(BASE + "/info")

    assert response.status_code == 500
    assert response.json()["detail"].startswith("Error reading log file info:")


async def test_should_raise_404_when_log_path_setting_is_absent(db_session):
    with pytest.raises(HTTPException) as excinfo:
        await get_log_file_path(db_session)

    assert excinfo.value.status_code == 404


async def test_should_raise_503_when_settings_are_not_configured(db_session):
    with pytest.raises(HTTPException) as excinfo:
        await admin_from_query_token(token="anything", db=db_session)

    assert excinfo.value.status_code == 503


async def test_should_raise_401_when_query_token_is_missing(db_session):
    with pytest.raises(HTTPException) as excinfo:
        await admin_from_query_token(token=None, db=db_session)

    assert excinfo.value.status_code == 401


@pytest.mark.parametrize(
    ("size", "expected"),
    [
        (512, "512.00 B"),
        (2048, "2.00 KB"),
        (5 * 1024 * 1024, "5.00 MB"),
        (3 * 1024 * 1024 * 1024, "3.00 GB"),
        (2 * 1024**4, "2.00 TB"),
    ],
)
def test_should_format_bytes_when_size_is_given(size, expected):
    assert format_bytes(size) == expected
