"""Tests for app.core.exceptions: error payload contracts."""
import json
import pytest
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, field_validator
from starlette.testclient import TestClient

from app.core.exceptions import (
    MultiFieldValidationError,
    ValidationError,
    custom_multi_field_validation_error_handler,
    custom_validation_error_handler,
    format_validation_errors,
    validation_exception_handler,
)


class TestValidationError:
    def test_should_wrap_single_message_in_list(self):
        exc = ValidationError("name", "Name is required")

        assert exc.field == "name"
        assert exc.messages == ["Name is required"]
        assert "name" in str(exc)

    def test_should_keep_message_list_as_is(self):
        exc = ValidationError("port", ["Too low", "Too high"])

        assert exc.messages == ["Too low", "Too high"]


class TestFormatValidationErrors:
    def test_should_prefix_fields_with_body(self):
        formatted = format_validation_errors({"name": ["required"]})

        assert formatted == {"errors": {"body.name": ["required"]}}

    def test_should_not_double_prefix_existing_body_prefix(self):
        formatted = format_validation_errors({"body.name": ["required"]})

        assert formatted == {"errors": {"body.name": ["required"]}}


@pytest.mark.asyncio
class TestCustomHandlers:
    async def test_should_return_422_with_field_errors_for_validation_error(self):
        response = await custom_validation_error_handler(
            None, ValidationError("listen_port", "must be 1-65535")
        )

        assert response.status_code == 422
        assert b"body.listen_port" in response.body

    async def test_should_return_422_with_all_fields_for_multi_field_error(self):
        response = await custom_multi_field_validation_error_handler(
            None,
            MultiFieldValidationError(
                {"name": ["required"], "port": ["out of range"]}
            ),
        )

        assert response.status_code == 422
        assert b"body.name" in response.body and b"body.port" in response.body


@pytest.mark.asyncio
class TestRequestValidationHandler:
    async def test_should_strip_value_error_prefix(self):
        exc = RequestValidationError(
            [{"loc": ("body", "name"), "msg": "Value error, is required", "type": "value_error"}]
        )

        response = await validation_exception_handler(None, exc)
        payload = json.loads(response.body)

        assert payload == {"errors": {"body.name": ["is required"]}}

    async def test_should_build_nested_field_keys(self):
        exc = RequestValidationError(
            [{"loc": ("body", "server", "endpoint"), "msg": "invalid", "type": "value_error"}]
        )

        payload = json.loads((await validation_exception_handler(None, exc)).body)

        assert payload == {"errors": {"body.server.endpoint": ["invalid"]}}

    async def test_should_attach_model_level_ip_error_to_both_ip_fields(self):
        exc = RequestValidationError(
            [{"loc": (), "msg": "At least one IP address (IPv4 or IPv6) is required", "type": "value_error"}]
        )

        payload = json.loads((await validation_exception_handler(None, exc)).body)
        errors = payload["errors"]

        assert "body.ipv4_address" in errors
        assert "body.ipv6_address" in errors

    async def test_should_attach_generic_model_level_error_to_form_key(self):
        exc = RequestValidationError(
            [{"loc": (), "msg": "Something is inconsistent", "type": "value_error"}]
        )

        payload = json.loads((await validation_exception_handler(None, exc)).body)

        assert payload == {"errors": {"body._form": ["Something is inconsistent"]}}

    async def test_should_accumulate_multiple_messages_for_same_field(self):
        exc = RequestValidationError(
            [
                {"loc": ("body", "name"), "msg": "too short", "type": "value_error"},
                {"loc": ("body", "name"), "msg": "bad chars", "type": "value_error"},
            ]
        )

        payload = json.loads((await validation_exception_handler(None, exc)).body)

        assert payload["errors"]["body.name"] == ["too short", "bad chars"]


class TestHandlerRegistrationThroughApp:
    """End-to-end check that the handlers are wired into the app."""

    @pytest.fixture
    def client(self):
        from app.main import app

        return TestClient(app, raise_server_exceptions=False)

    def test_should_render_custom_validation_error_as_422(self, client):
        from app.core.exceptions import MultiFieldValidationError

        app = client.app
        path = "/__test/validation-error"

        @app.post(path)
        async def _raise():
            raise MultiFieldValidationError({"name": ["Name is required"]})

        try:
            response = client.post(path)
            assert response.status_code == 422
            assert response.json() == {"errors": {"body.name": ["Name is required"]}}
        finally:
            app.router.routes = [r for r in app.router.routes if getattr(r, "path", None) != path]

    def test_should_render_pydantic_request_validation_error(self, client):
        app = client.app
        path = "/__test/pydantic"

        class Body(BaseModel):
            port: int

            @field_validator("port")
            @classmethod
            def _positive(cls, value):
                if value <= 0:
                    raise ValueError("must be positive")
                return value

        @app.post(path)
        async def _create(body: Body):
            return {"port": body.port}

        try:
            response = client.post(path, json={"port": -5})
            assert response.status_code == 422
            errors = response.json()["errors"]
            assert "body.port" in errors
            assert "must be positive" in errors["body.port"][0]
        finally:
            app.router.routes = [r for r in app.router.routes if getattr(r, "path", None) != path]
