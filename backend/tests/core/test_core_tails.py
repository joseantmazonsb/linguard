"""Coverage for the remaining defensive branches of core/utils helpers."""
from unittest.mock import MagicMock, patch

import pytest

from app.core import database as app_database
from app.core import security as security_module
from app.utils import validation as validation_utils


class TestReinitEngineDisposal:
    async def test_should_dispose_previous_engine_when_loop_is_running(self, api_db):
        previous = app_database.engine

        app_database.reinit_engine("sqlite+aiosqlite://")
        await previous.dispose()

        assert app_database.engine is not previous

    def test_should_work_without_previous_engine(self, monkeypatch, tmp_path):
        old_engine = app_database.engine
        old_session = app_database.AsyncSessionLocal
        monkeypatch.setattr(app_database, "engine", None)
        try:
            app_database.reinit_engine(f"sqlite+aiosqlite:///{tmp_path}/fresh.db")
            assert app_database.engine is not None
        finally:
            app_database.engine = old_engine
            app_database.AsyncSessionLocal = old_session

    def test_should_ignore_errors_while_disposing_previous_engine(self, monkeypatch):
        broken_engine = MagicMock()
        broken_engine.dispose.side_effect = RuntimeError("already closed")
        monkeypatch.setattr(app_database, "engine", broken_engine)

        # Disposal is best effort: whatever happens to the old engine, the new
        # one must be installed and no exception may escape.
        app_database.reinit_engine("sqlite+aiosqlite://")

        assert app_database.engine is not broken_engine


class TestSettingsForAuthFailure:
    async def test_should_return_none_when_query_fails(self, db_session):
        db_session.execute = MagicMock(side_effect=RuntimeError("no such table"))

        assert await security_module.get_settings_for_auth(db_session) is None


class TestConfigLoaderSaveFailure:
    def test_should_raise_runtime_error_when_file_cannot_be_written(
        self, tmp_path, monkeypatch
    ):
        from app.core.config_loader import ConfigLoader

        loader = ConfigLoader(config_path=tmp_path / "linguard.config.json")

        def boom(*_args, **_kwargs):
            raise OSError("disk full")

        monkeypatch.setattr("builtins.open", boom)

        with pytest.raises(RuntimeError, match="Failed to save"):
            loader.save({"database": {}})


class TestValidationTails:
    def test_should_raise_custom_type_error_without_value_error_prefix(self):
        from pydantic_core import PydanticCustomError

        with pytest.raises(PydanticCustomError) as exc_info:
            validation_utils._raise_validation_error("must be positive")

        assert "must be positive" in str(exc_info.value)

    def test_should_reject_hostname_longer_than_253_characters(self):
        hostname = ".".join(["a" * 60] * 5)

        with pytest.raises(ValueError, match="must not exceed 253 characters"):
            validation_utils.validate_endpoint(hostname, field_name="Endpoint")

    def test_should_reject_email_longer_than_254_characters(self):
        local = "a" * 250

        with pytest.raises(ValueError, match="must not exceed 254 characters"):
            validation_utils.validate_email(f"{local}@example.com", field_name="Email")
