"""
Tests for Telegram helper functions in ``app/api/integrations.py``.

The function under test builds its own ``httpx.AsyncClient``, so the client
class is replaced with a small fake that implements the async context manager
protocol. This keeps the test close to the production code path (same URL
building, same response handling, same exception mapping) without hitting the
network.
"""
import httpx
import pytest
from unittest.mock import patch

from app.api.integrations import fetch_telegram_chat_id


class FakeResponse:
    """Minimal stand-in for an httpx.Response."""

    def __init__(self, data=None, error=None):
        self._data = data if data is not None else {}
        self._error = error
        self.status_code = 200

    def raise_for_status(self):
        if self._error is not None:
            raise self._error

    def json(self):
        return self._data


class FakeAsyncClient:
    """Async context manager that yields itself and records requested URLs."""

    def __init__(self, response):
        self._response = response
        self.requested_urls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url, **kwargs):
        self.requested_urls.append(url)
        if isinstance(self._response, Exception):
            raise self._response
        return self._response


def _patch_client(response):
    """Patch httpx.AsyncClient inside the integrations module with a fake."""
    holder = {}

    def factory(*args, **kwargs):
        holder["client"] = FakeAsyncClient(response)
        return holder["client"]

    patcher = patch("app.api.integrations.httpx.AsyncClient", factory)
    return patcher, holder


class TestFetchTelegramChatId:
    """Tests for fetch_telegram_chat_id."""

    @pytest.mark.asyncio
    async def test_fetch_telegram_chat_id_success(self):
        response = FakeResponse(
            {
                "ok": True,
                "result": [{"message": {"chat": {"id": 123456}}}],
            }
        )
        patcher, holder = _patch_client(response)
        with patcher:
            chat_id = await fetch_telegram_chat_id("123456:ABC-DEF")

        assert chat_id == "123456"
        assert holder["client"].requested_urls == [
            "https://api.telegram.org/bot123456:ABC-DEF/getUpdates"
        ]

    @pytest.mark.asyncio
    async def test_fetch_telegram_chat_id_returns_first_chat_when_multiple(self):
        response = FakeResponse(
            {
                "ok": True,
                "result": [
                    {"message": {"chat": {"id": 111}}},
                    {"message": {"chat": {"id": 222}}},
                ],
            }
        )
        patcher, _ = _patch_client(response)
        with patcher:
            chat_id = await fetch_telegram_chat_id("token")

        assert chat_id == "111"

    @pytest.mark.asyncio
    async def test_fetch_telegram_chat_id_empty_result(self):
        patcher, _ = _patch_client(FakeResponse({"ok": True, "result": []}))
        with patcher:
            with pytest.raises(Exception) as exc_info:
                await fetch_telegram_chat_id("token")

        assert "Cannot fetch chat ID" in str(exc_info.value)
        assert "send a message" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_fetch_telegram_chat_id_ok_false_invalid_token(self):
        patcher, _ = _patch_client(
            FakeResponse({"ok": False, "description": "Unauthorized"})
        )
        with patcher:
            with pytest.raises(Exception) as exc_info:
                await fetch_telegram_chat_id("invalid_token")

        assert "Invalid bot token" in str(exc_info.value)
        assert "Unauthorized" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_fetch_telegram_chat_id_http_error_status(self):
        request = httpx.Request("GET", "https://api.telegram.org")
        response = httpx.Response(401, request=request, json={"ok": False})
        error = httpx.HTTPStatusError(
            "401 Unauthorized", request=request, response=response
        )

        patcher, _ = _patch_client(FakeResponse(error=error))
        with patcher:
            with pytest.raises(Exception) as exc_info:
                await fetch_telegram_chat_id("invalid_token")

        assert "Failed to connect to Telegram API" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_fetch_telegram_chat_id_network_error(self):
        patcher, _ = _patch_client(
            httpx.ConnectError("connection refused")
        )
        with patcher:
            with pytest.raises(Exception) as exc_info:
                await fetch_telegram_chat_id("token")

        assert "Failed to connect to Telegram API" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_fetch_telegram_chat_id_missing_chat(self):
        patcher, _ = _patch_client(
            FakeResponse({"ok": True, "result": [{"message": {"text": "hi"}}]})
        )
        with patcher:
            with pytest.raises(Exception) as exc_info:
                await fetch_telegram_chat_id("token")

        assert "Could not extract chat ID" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_fetch_telegram_chat_id_missing_message(self):
        patcher, _ = _patch_client(
            FakeResponse({"ok": True, "result": [{"foo": "bar"}]})
        )
        with patcher:
            with pytest.raises(Exception) as exc_info:
                await fetch_telegram_chat_id("token")

        assert "Could not extract chat ID" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_fetch_telegram_chat_id_zero_chat_id_rejected(self):
        # A chat id of 0 is falsy; the implementation rejects it. Documents
        # current behaviour so a future fix is a deliberate decision.
        patcher, _ = _patch_client(
            FakeResponse({"ok": True, "result": [{"message": {"chat": {"id": 0}}}]})
        )
        with patcher:
            with pytest.raises(Exception) as exc_info:
                await fetch_telegram_chat_id("token")

        assert "Could not extract chat ID" in str(exc_info.value)
