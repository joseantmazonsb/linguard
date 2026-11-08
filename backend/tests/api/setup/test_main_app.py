"""Tests for app.main: exception handling, health, monitors, logging and the
startup lifespan logic.

The lifespan is driven directly (never through TestClient) so that no real
background task, GitHub update check or plugin is ever started: every external
service the startup touches is replaced with a recorder.
"""

import importlib.util
import json
import logging
import sys
from pathlib import Path
from typing import ClassVar
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import delete, select

from app.core import database as app_database
from app.core.config_loader import config_loader
from app.core.events import EventType, event_bus
from app.core.exceptions import (
    MultiFieldValidationError,
    ValidationError,
    custom_multi_field_validation_error_handler,
    custom_validation_error_handler,
    validation_exception_handler,
)
from app.main import (
    app,
    configure_logging,
    lifespan,
    start_background_monitors,
    stop_background_monitors,
)
from app.models.integration import Integration
from app.models.server import Server
from app.models.settings import GlobalSettings

MAIN_PATH = Path(sys.modules["app.main"].__file__)


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

class FakeMonitor:
    def __init__(self, name="monitor", fail_on_start=False):
        self.name = name
        self._running = False
        self.starts = 0
        self.stops = 0
        self.fail_on_start = fail_on_start

    async def start(self):
        if self.fail_on_start:
            raise RuntimeError(f"{self.name} cannot start")
        self.starts += 1
        self._running = True

    async def stop(self):
        self.stops += 1
        self._running = False

    async def check_health(self):
        return {"status": "healthy", "checks": {"database": True}}


class FakeUpdateChecker:
    instances: ClassVar[list] = []

    def __init__(self, version_service, notification_service, check_interval_hours=6):
        self.args = (version_service, notification_service, check_interval_hours)
        self.started = False
        self.stopped = False
        FakeUpdateChecker.instances.append(self)

    async def start(self):
        self.started = True

    async def stop(self):
        self.stopped = True


class FakePluginManager:
    def __init__(self, plugins_dir=None, discover_raises=None):
        self.plugins_dir = plugins_dir
        self.discover_raises = discover_raises
        self.discovered = 0
        self.loaded = 0
        self.unloaded = 0

    async def discover_plugins(self, plugins_directory, db):
        if self.discover_raises:
            raise self.discover_raises
        self.plugins_dir = plugins_directory
        return 2

    async def load_enabled_plugins(self, db):
        self.loaded += 1

    def loaded_count(self) -> int:
        return 2

    async def unload_all(self):
        self.unloaded += 1


class FakeIntegrationService:
    def __init__(self, create_raises=None):
        self.created = []
        self.dispatched = []
        self.create_raises = create_raises
        self.dispatch_raises = None

    async def create_integration(self, db, name, type, config, events_subscribed, description=None, enabled=True):
        if self.create_raises:
            raise self.create_raises
        self.created.append({"name": name, "type": type, "events": events_subscribed})

        class _Integration:
            id = 1

        return _Integration()

    async def dispatch_event_to_integrations(self, db, event_type, event_data):
        if self.dispatch_raises:
            raise self.dispatch_raises
        self.dispatched.append((event_type, event_data))


class FakeWireGuardForAutostart:
    def __init__(self, results=None, raises_for=None):
        self.results = results or {}
        self.raises_for = raises_for or set()
        self.started_servers = []

    async def start_interface(self, db, server_id, interface):
        if server_id in self.raises_for:
            raise RuntimeError(f"cannot start server {server_id}")
        self.started_servers.append(server_id)
        return self.results.get(server_id, True)

    def find_interface_by_key(self, *args, **kwargs):
        return "wg9"

    def find_interface_by_public_key(self, public_key):
        return "wg9"


@pytest.fixture
def fake_monitors():
    monitors = {
        "health_monitor_service": FakeMonitor("health"),
        "interface_monitor_service": FakeMonitor("interface"),
        "backup_cleanup_service": FakeMonitor("backup-cleanup"),
        "periodic_backup_service": FakeMonitor("periodic-backup"),
        "metrics_monitor_service": FakeMonitor("metrics"),
    }
    with patch.object(app.container, "health_monitor_service", lambda: monitors["health_monitor_service"]), \
         patch.object(app.container, "interface_monitor_service", lambda: monitors["interface_monitor_service"]), \
         patch.object(app.container, "backup_cleanup_service", lambda: monitors["backup_cleanup_service"]), \
         patch.object(app.container, "periodic_backup_service", lambda: monitors["periodic_backup_service"]), \
         patch.object(app.container, "metrics_monitor_service", lambda: monitors["metrics_monitor_service"]):
        yield monitors


@pytest.fixture
def reset_monitor_globals():
    import app.main as main_module

    saved = (
        main_module._health_monitor,
        main_module._interface_monitor,
        main_module._backup_cleanup,
        main_module._periodic_backup,
        main_module._metrics_monitor,
    )
    yield main_module
    (
        main_module._health_monitor,
        main_module._interface_monitor,
        main_module._backup_cleanup,
        main_module._periodic_backup,
        main_module._metrics_monitor,
    ) = saved


@pytest.fixture
def captured_handlers():
    """Capture the handlers the lifespan registers instead of polluting the bus."""
    handlers = []

    def _subscribe(event_type, handler):
        handlers.append((event_type, handler))

    with patch.object(event_bus, "subscribe", _subscribe):
        yield handlers


# ---------------------------------------------------------------------------
# Exception handlers
# ---------------------------------------------------------------------------

def _request() -> Request:
    return Request({"type": "http", "method": "POST", "path": "/x", "headers": []})


@pytest.mark.asyncio
async def test_should_prefix_body_when_custom_validation_error_handled():
    response = await custom_validation_error_handler(_request(), ValidationError("email", "Taken"))

    assert response.status_code == 422
    assert response.body == b'{"errors":{"body.email":["Taken"]}}'


@pytest.mark.asyncio
async def test_should_format_all_fields_when_multi_field_validation_error_handled():
    exc = MultiFieldValidationError({"name": ["required"], "body.port": ["range"]})

    response = await custom_multi_field_validation_error_handler(_request(), exc)

    assert response.status_code == 422
    assert response.body == (
        b'{"errors":{"body.name":["required"],"body.port":["range"]}}'
    )


@pytest.mark.asyncio
async def test_should_strip_value_error_prefix_when_request_validation_fails():
    from app.schemas.setup import ConfigureGlobals

    try:
        ConfigureGlobals(secret_key="short")
    except PydanticValidationError as e:
        exc = RequestValidationError(e.errors())

    response = await validation_exception_handler(_request(), exc)
    body = json.loads(response.body)

    assert response.status_code == 422
    assert body["errors"]["body.secret_key"] == [
        "Secret key must be at least 32 characters long for security"
    ]


@pytest.mark.asyncio
async def test_should_attach_ip_model_error_to_both_ip_fields():
    from app.schemas.server import ServerCreate

    try:
        ServerCreate(
            name="main",
            endpoint="vpn.example.com",
            listen_port=51820,
            ipv4_address=None,
            ipv6_address=None,
            public_key="pub",
            private_key="priv",
        )
    except PydanticValidationError as e:
        exc = RequestValidationError(e.errors())

    body = json.loads((await validation_exception_handler(_request(), exc)).body)

    expected = "At least one IP address (IPv4 or IPv6) is required"
    assert body["errors"]["body.ipv4_address"] == [expected]
    assert body["errors"]["body.ipv6_address"] == [expected]


@pytest.mark.asyncio
async def test_should_use_form_key_when_model_error_is_generic():
    exc = RequestValidationError(
        [{"loc": (), "msg": "Something is wrong", "type": "value_error"}]
    )

    body = json.loads((await validation_exception_handler(_request(), exc)).body)

    assert body["errors"] == {"body._form": ["Something is wrong"]}


@pytest.mark.asyncio
async def test_should_return_422_via_http_when_endpoint_raises_custom_validation_error(auth_client):
    response = auth_client.put("/api/v1/auth/users/1", json={"role": "standard"})

    assert response.status_code == 422
    assert response.json() == {"errors": {"body.role": ["Cannot demote the last administrator"]}}


# ---------------------------------------------------------------------------
# /health
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_should_report_unavailable_when_health_monitor_not_running(api_client, reset_monitor_globals):
    reset_monitor_globals._health_monitor = None

    response = api_client.get("/health")

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable", "message": "Setup not complete"}


@pytest.mark.asyncio
async def test_should_report_unavailable_when_health_monitor_is_stopped(api_client, reset_monitor_globals):
    monitor = FakeMonitor()
    reset_monitor_globals._health_monitor = monitor

    response = api_client.get("/health")

    assert response.status_code == 503


@pytest.mark.asyncio
async def test_should_delegate_to_health_monitor_when_running(api_client, reset_monitor_globals):
    monitor = FakeMonitor()
    monitor._running = True
    reset_monitor_globals._health_monitor = monitor

    response = api_client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "checks": {"database": True}}


# ---------------------------------------------------------------------------
# configure_logging
# ---------------------------------------------------------------------------

def test_should_write_to_file_and_create_directory_when_log_path_given(tmp_path):
    log_file = tmp_path / "nested" / "dir" / "linguard.log"

    configure_logging(str(log_file))

    root = logging.getLogger()
    try:
        assert any(
            isinstance(h, logging.FileHandler) and Path(h.baseFilename) == log_file
            for h in root.handlers
        )
        assert root.level == logging.INFO
        log_file.write_text("")
        assert log_file.exists()
    finally:
        for handler in root.handlers[:]:
            root.removeHandler(handler)
            handler.close()
        configure_logging()


def test_should_resolve_relative_log_path_against_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    configure_logging("relative/logs/app.log")

    root = logging.getLogger()
    try:
        assert (tmp_path / "relative" / "logs" / "app.log").exists()
    finally:
        for handler in root.handlers[:]:
            root.removeHandler(handler)
            handler.close()
        configure_logging()


def test_should_use_console_handler_when_no_log_path():
    configure_logging(None)

    root = logging.getLogger()
    try:
        assert any(isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)
                   for h in root.handlers)
    finally:
        for handler in root.handlers[:]:
            root.removeHandler(handler)
            handler.close()
        configure_logging()


# ---------------------------------------------------------------------------
# start_background_monitors / stop_background_monitors
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_should_not_start_monitors_when_engine_is_absent(api_db, fake_monitors, reset_monitor_globals):
    with patch.object(app_database, "engine", None):
        await start_background_monitors()

    assert reset_monitor_globals._health_monitor is None
    assert all(m.starts == 0 for m in fake_monitors.values())


@pytest.mark.asyncio
async def test_should_start_each_monitor_once_when_called_repeatedly(api_db, fake_monitors, reset_monitor_globals):
    await start_background_monitors()
    await start_background_monitors()

    assert all(m.starts == 1 for m in fake_monitors.values())
    assert reset_monitor_globals._health_monitor is fake_monitors["health_monitor_service"]
    assert reset_monitor_globals._metrics_monitor is fake_monitors["metrics_monitor_service"]


@pytest.mark.asyncio
async def test_should_stop_and_forget_all_monitors_when_stop_called(api_db, fake_monitors, reset_monitor_globals):
    await start_background_monitors()

    await stop_background_monitors()

    assert all(m.stops == 1 for m in fake_monitors.values())
    assert reset_monitor_globals._health_monitor is None
    assert reset_monitor_globals._interface_monitor is None
    assert reset_monitor_globals._backup_cleanup is None
    assert reset_monitor_globals._periodic_backup is None
    assert reset_monitor_globals._metrics_monitor is None

    # After a reset the monitors can be started again.
    await start_background_monitors()
    assert all(m.starts == 2 for m in fake_monitors.values())


@pytest.mark.asyncio
async def test_should_be_noop_when_stopping_without_started_monitors(reset_monitor_globals):
    await stop_background_monitors()

    assert reset_monitor_globals._health_monitor is None


# ---------------------------------------------------------------------------
# Lifespan: fresh install (no config file, no engine)
# ---------------------------------------------------------------------------

@pytest.fixture
def fake_update_checker():
    FakeUpdateChecker.instances = []
    with patch("app.services.update_checker.UpdateCheckerService", FakeUpdateChecker):
        yield FakeUpdateChecker


@pytest.fixture
def recorded_logging_config():
    """Keep the lifespan from touching the real logging configuration."""
    calls = []
    with patch("app.main.configure_logging", calls.append):
        yield calls


@pytest.mark.asyncio
async def test_should_skip_database_steps_when_config_file_missing_on_startup(
    tmp_path, monkeypatch, reset_monitor_globals, captured_handlers, fake_update_checker
):
    monkeypatch.setattr(config_loader, "config_path", tmp_path / "missing.json")
    plugin_manager = FakePluginManager()
    integration_service = FakeIntegrationService()

    init_engine_calls = []
    with patch.object(app_database, "engine", None), \
         patch.object(app_database, "AsyncSessionLocal", None), \
         patch("app.core.database.init_engine", lambda: init_engine_calls.append(True)), \
         patch.object(app.container, "integration_service", lambda: integration_service), \
         patch.object(app.container, "plugin_manager", lambda: plugin_manager):
        async with lifespan(app):
            assert app_database.engine is None

    assert init_engine_calls == []
    assert integration_service.created == []
    assert plugin_manager.discovered == 0
    assert plugin_manager.unloaded == 1
    checker = fake_update_checker.instances[0]
    assert checker.started is True and checker.stopped is True
    # Event handlers for the bus were still registered for later use.
    subscribed = {event_type for event_type, _ in captured_handlers}
    assert EventType.SERVER_STARTED in subscribed
    assert EventType.PEER_CREATED in subscribed


@pytest.mark.asyncio
async def test_should_warn_when_plugin_manager_fails_to_unload_on_shutdown(
    tmp_path, monkeypatch, reset_monitor_globals, captured_handlers, fake_update_checker
):
    monkeypatch.setattr(config_loader, "config_path", tmp_path / "missing.json")

    class BrokenPluginManager(FakePluginManager):
        async def unload_all(self):
            raise RuntimeError("unload failed")

    with patch.object(app_database, "engine", None), \
         patch.object(app.container, "integration_service", lambda: FakeIntegrationService()), \
         patch.object(app.container, "plugin_manager", lambda: BrokenPluginManager()):
        async with lifespan(app):
            pass  # shutdown path must swallow the error


# ---------------------------------------------------------------------------
# Lifespan: existing install, setup complete
# ---------------------------------------------------------------------------

async def _seed_existing_install(session, *, setup_completed=True, log_path="./linguard.log"):
    session.add(
        GlobalSettings(
            secret_key="k" * 40,
            backup_dir="./backups",
            log_path=log_path,
            plugins_directory="/tmp/plugins",
            setup_completed=setup_completed,
        )
    )
    await session.commit()


async def _add_server(session, name, autostart=True, status="stopped", interface="wg0"):
    server = Server(
        name=name,
        interface=interface,
        endpoint="vpn.example.com",
        listen_port=51820,
        private_key="priv",
        public_key=f"pub-{name}",
        ipv4_address="10.0.0.1/24",
        autostart=autostart,
        status=status,
    )
    session.add(server)
    await session.commit()
    await session.refresh(server)
    return server


@pytest.mark.asyncio
async def test_should_initialise_engine_integrations_plugins_and_autostart_when_setup_complete(
    api_db, db_session, tmp_path, monkeypatch, fake_monitors, reset_monitor_globals,
    captured_handlers, fake_update_checker,
):
    monkeypatch.setattr(config_loader, "config_path", tmp_path / "linguard.config.json")
    (tmp_path / "linguard.config.json").write_text("{}")
    await _seed_existing_install(db_session)
    running = await _add_server(db_session, "wg-running", status="running", interface="wg1")
    healthy = await _add_server(db_session, "wg-ok", interface="wg2")
    broken = await _add_server(db_session, "wg-broken", interface="wg3")
    explosive = await _add_server(db_session, "wg-explosive", interface="wg4")
    after_failure = await _add_server(db_session, "wg-after", interface="wg5")

    plugin_manager = FakePluginManager()
    wireguard = FakeWireGuardForAutostart(
        results={broken.id: False}, raises_for={explosive.id}
    )
    configure_logging_calls = []

    with patch("app.main.init_engine") as init_engine, \
         patch("app.main.configure_logging", configure_logging_calls.append), \
         patch.object(app.container, "plugin_manager", lambda: plugin_manager), \
         patch.object(app.container, "wireguard_service", lambda: wireguard):
        async with lifespan(app):
            init_engine.assert_called_once()
            assert all(m.starts == 1 for m in fake_monitors.values())

    # Startup logging was reconfigured from the database settings.
    assert configure_logging_calls == ["./linguard.log"]

    # Default in-app notification integration was created exactly once.
    integrations = (await db_session.execute(select(Integration))).scalars().all()
    assert [i.name for i in integrations] == ["In-App Notifications"]

    # Plugin discovery/loading used the configured directory.
    assert plugin_manager.plugins_dir == "/tmp/plugins"
    assert plugin_manager.loaded == 1
    assert plugin_manager.unloaded == 1

    # Autostart: running servers skipped, successful ones marked running,
    # failures rolled back instead of aborting startup.
    assert healthy.id in wireguard.started_servers
    assert broken.id in wireguard.started_servers
    assert after_failure.id in wireguard.started_servers
    await db_session.refresh(healthy)
    await db_session.refresh(running)
    await db_session.refresh(broken)
    await db_session.refresh(after_failure)
    assert healthy.status == "running"
    assert running.status == "running"
    assert broken.status == "stopped"
    assert after_failure.status == "running"

    # Shutdown stopped the monitors and the update checker.
    assert all(m.stops == 1 for m in fake_monitors.values())
    assert fake_update_checker.instances[0].stopped is True


@pytest.mark.asyncio
async def test_should_dispatch_events_to_integrations_when_bus_handler_runs(
    api_db, db_session, tmp_path, monkeypatch, fake_monitors, reset_monitor_globals,
    captured_handlers, fake_update_checker, recorded_logging_config,
):
    (tmp_path / "linguard.config.json").write_text("{}")
    monkeypatch.setattr(config_loader, "config_path", tmp_path / "linguard.config.json")
    await _seed_existing_install(db_session)
    integration_service = FakeIntegrationService()

    with patch("app.main.init_engine"), \
         patch.object(app.container, "integration_service", lambda: integration_service), \
         patch.object(app.container, "plugin_manager", lambda: FakePluginManager()):
        async with lifespan(app):
            handler = next(
                h for event_type, h in captured_handlers if event_type == EventType.PEER_CREATED
            )
            await handler(
                {
                    "event_type": EventType.PEER_CREATED.value,
                    "source_type": "peer",
                    "source_id": 5,
                    "payload": {"name": "laptop"},
                    "user_id": None,
                }
            )

    assert len(integration_service.dispatched) == 1
    event_type, event_data = integration_service.dispatched[0]
    assert event_type is EventType.PEER_CREATED
    assert event_data["source_id"] == 5

    # A failing integration must not escape the handler.
    integration_service.dispatch_raises = RuntimeError("integration down")
    await handler({"event_type": EventType.PEER_CREATED.value, "source_id": 6})
    assert len(integration_service.dispatched) == 1

    # When the engine goes away mid-flight the handler must not explode either.
    integration_service.dispatch_raises = None
    with patch.object(app_database, "engine", None):
        await handler({"event_type": EventType.PEER_CREATED.value})
    assert len(integration_service.dispatched) == 1


@pytest.mark.asyncio
async def test_should_broadcast_status_when_server_event_handler_runs(
    api_db, db_session, tmp_path, monkeypatch, fake_monitors, reset_monitor_globals,
    captured_handlers, fake_update_checker, recorded_logging_config,
):
    (tmp_path / "linguard.config.json").write_text("{}")
    monkeypatch.setattr(config_loader, "config_path", tmp_path / "linguard.config.json")
    await _seed_existing_install(db_session)
    broadcasts = []

    async def _broadcast(payload):
        broadcasts.append(payload)
        if len(broadcasts) == 2:
            raise RuntimeError("websocket layer down")

    with patch("app.main.init_engine"), \
         patch.object(app.container, "integration_service", lambda: FakeIntegrationService()), \
         patch.object(app.container, "plugin_manager", lambda: FakePluginManager()), \
         patch("app.api.ws.broadcast_server_status_change", AsyncMock(side_effect=_broadcast)):
        async with lifespan(app):
            status_handlers = [
                h for event_type, h in captured_handlers
                if event_type == EventType.SERVER_STARTED
            ]
            # One dispatcher handler for all events + the status broadcaster.
            assert len(status_handlers) == 2
            await status_handlers[-1](
                {
                    "event_type": EventType.SERVER_STARTED.value,
                    "source_id": 3,
                    "payload": {"name": "wg0", "status": "running", "detected": True},
                }
            )
            # A failing broadcast is swallowed by the handler.
            await status_handlers[-1](
                {
                    "event_type": EventType.SERVER_STARTED.value,
                    "source_id": 4,
                    "payload": {"name": "wg1", "status": "running"},
                }
            )

    assert broadcasts == [
        {
            "server_id": 3,
            "name": "wg0",
            "status": "running",
            "event_type": EventType.SERVER_STARTED.value,
            "detected": True,
        },
        {
            "server_id": 4,
            "name": "wg1",
            "status": "running",
            "event_type": EventType.SERVER_STARTED.value,
            "detected": False,
        },
    ]


@pytest.mark.asyncio
async def test_should_reuse_existing_integration_when_already_present(
    api_db, db_session, tmp_path, monkeypatch, fake_monitors, reset_monitor_globals,
    captured_handlers, fake_update_checker, recorded_logging_config,
):
    (tmp_path / "linguard.config.json").write_text("{}")
    monkeypatch.setattr(config_loader, "config_path", tmp_path / "linguard.config.json")
    await _seed_existing_install(db_session)
    db_session.add(
        Integration(
            name="In-App Notifications",
            type="notification",
            config={},
            events_subscribed=[],
            enabled=True,
        )
    )
    await db_session.commit()

    with patch("app.main.init_engine"), \
         patch.object(app.container, "plugin_manager", lambda: FakePluginManager()):
        async with lifespan(app):
            pass

    integrations = (await db_session.execute(select(Integration))).scalars().all()
    assert len(integrations) == 1


@pytest.mark.asyncio
async def test_should_keep_starting_when_integration_setup_fails(
    api_db, db_session, tmp_path, monkeypatch, fake_monitors, reset_monitor_globals,
    captured_handlers, fake_update_checker, recorded_logging_config,
):
    (tmp_path / "linguard.config.json").write_text("{}")
    monkeypatch.setattr(config_loader, "config_path", tmp_path / "linguard.config.json")
    await _seed_existing_install(db_session)
    failing = FakeIntegrationService(create_raises=RuntimeError("integration table broken"))

    with patch("app.main.init_engine"), \
         patch.object(app.container, "integration_service", lambda: failing), \
         patch.object(app.container, "plugin_manager", lambda: FakePluginManager()):
        async with lifespan(app):
            assert all(m.starts == 1 for m in fake_monitors.values())

    assert failing.created == []


@pytest.mark.asyncio
async def test_should_keep_starting_when_plugin_discovery_fails(
    api_db, db_session, tmp_path, monkeypatch, fake_monitors, reset_monitor_globals,
    captured_handlers, fake_update_checker, recorded_logging_config,
):
    (tmp_path / "linguard.config.json").write_text("{}")
    monkeypatch.setattr(config_loader, "config_path", tmp_path / "linguard.config.json")
    await _seed_existing_install(db_session)
    plugin_manager = FakePluginManager(discover_raises=RuntimeError("plugin directory unreadable"))

    with patch("app.main.init_engine"), \
         patch.object(app.container, "plugin_manager", lambda: plugin_manager):
        async with lifespan(app):
            assert all(m.starts == 1 for m in fake_monitors.values())

    assert plugin_manager.loaded == 0
    assert plugin_manager.unloaded == 1


@pytest.mark.asyncio
async def test_should_warn_when_logging_cannot_be_configured_from_database(
    api_db, db_session, tmp_path, monkeypatch, fake_monitors, reset_monitor_globals,
    captured_handlers, fake_update_checker,
):
    (tmp_path / "linguard.config.json").write_text("{}")
    monkeypatch.setattr(config_loader, "config_path", tmp_path / "linguard.config.json")
    await _seed_existing_install(db_session)

    def _broken_logging(path):
        raise PermissionError(f"cannot write {path}")

    with patch("app.main.init_engine"), \
         patch("app.main.configure_logging", _broken_logging), \
         patch.object(app.container, "plugin_manager", lambda: FakePluginManager()):
        async with lifespan(app):
            assert all(m.starts == 1 for m in fake_monitors.values())


@pytest.mark.asyncio
async def test_should_skip_server_deleted_during_autostart(
    api_db, db_session, tmp_path, monkeypatch, fake_monitors, reset_monitor_globals,
    captured_handlers, fake_update_checker, recorded_logging_config,
):
    (tmp_path / "linguard.config.json").write_text("{}")
    monkeypatch.setattr(config_loader, "config_path", tmp_path / "linguard.config.json")
    await _seed_existing_install(db_session)
    doomed = await _add_server(db_session, "wg-doomed", interface="wg7")
    survivor = await _add_server(db_session, "wg-survivor", interface="wg8")

    class DeletingWireGuard(FakeWireGuardForAutostart):
        async def start_interface(self, db, server_id, interface):
            # The server is removed by another request while autostart runs.
            await db.execute(delete(Server).where(Server.id == doomed.id))
            await db.commit()
            self.started_servers.append(server_id)
            return True

    wireguard = DeletingWireGuard()

    with patch("app.main.init_engine"), \
         patch.object(app.container, "plugin_manager", lambda: FakePluginManager()), \
         patch.object(app.container, "wireguard_service", lambda: wireguard):
        async with lifespan(app):
            pass

    await db_session.refresh(survivor)
    assert survivor.status == "running"
    remaining = (await db_session.execute(select(Server))).scalars().all()
    assert [s.name for s in remaining] == ["wg-survivor"]


@pytest.mark.asyncio
async def test_should_keep_running_when_wireguard_service_unavailable_at_autostart(
    api_db, db_session, tmp_path, monkeypatch, fake_monitors, reset_monitor_globals,
    captured_handlers, fake_update_checker, recorded_logging_config,
):
    (tmp_path / "linguard.config.json").write_text("{}")
    monkeypatch.setattr(config_loader, "config_path", tmp_path / "linguard.config.json")
    await _seed_existing_install(db_session)
    await _add_server(db_session, "wg-ok", interface="wg9")

    def _explode():
        raise RuntimeError("wireguard service unavailable")

    with patch("app.main.init_engine"), \
         patch.object(app.container, "plugin_manager", lambda: FakePluginManager()), \
         patch.object(app.container, "wireguard_service", _explode):
        async with lifespan(app):
            # Monitors were already started before autostart failed.
            assert all(m.starts == 1 for m in fake_monitors.values())

    server = (await db_session.execute(select(Server))).scalars().one()
    await db_session.refresh(server)
    assert server.status == "stopped"


@pytest.mark.asyncio
async def test_should_skip_integration_plugins_and_autostart_when_setup_not_complete(
    api_db, db_session, tmp_path, monkeypatch, fake_monitors, reset_monitor_globals,
    captured_handlers, fake_update_checker, recorded_logging_config,
):
    (tmp_path / "linguard.config.json").write_text("{}")
    monkeypatch.setattr(config_loader, "config_path", tmp_path / "linguard.config.json")
    await _seed_existing_install(db_session, setup_completed=False)
    await _add_server(db_session, "wg-ok")
    plugin_manager = FakePluginManager(discover_raises=RuntimeError("bad plugin dir"))
    wireguard = FakeWireGuardForAutostart()

    with patch("app.main.init_engine"), \
         patch.object(app.container, "plugin_manager", lambda: plugin_manager), \
         patch.object(app.container, "wireguard_service", lambda: wireguard):
        async with lifespan(app):
            pass

    integrations = (await db_session.execute(select(Integration))).scalars().all()
    assert integrations == []
    assert plugin_manager.loaded == 0
    assert wireguard.started_servers == []


# ---------------------------------------------------------------------------
# Frontend static serving (module executed against a temp build directory)
# ---------------------------------------------------------------------------

@pytest.fixture
def static_app(tmp_path, monkeypatch):
    frontend = tmp_path / "frontend-build"
    (frontend / "assets").mkdir(parents=True)
    (frontend / "index.html").write_text("<html>linguard-spa</html>")
    (frontend / "assets" / "app.js").write_text("console.log('linguard')")
    (frontend / "favicon.ico").write_text("icon-bytes")

    monkeypatch.setenv("LINGUARD_FRONTEND_DIR", str(frontend))

    root_logger = logging.getLogger()
    saved_handlers = root_logger.handlers[:]

    class _StubContainer:
        """Stand-in so re-executing app.main never re-wires the real container."""

        def wire(self, *args, **kwargs):
            return None

    spec = importlib.util.spec_from_file_location("app.main_static_variant", MAIN_PATH)
    module = importlib.util.module_from_spec(spec)
    # The exported app already wired the real container into app.api; wiring a
    # throw-away instance would rebind every route dependency of the live app.
    monkeypatch.setattr("app.core.containers.Container", _StubContainer)
    spec.loader.exec_module(module)

    try:
        yield module
    finally:
        for handler in root_logger.handlers[:]:
            if handler not in saved_handlers:
                root_logger.removeHandler(handler)
        for handler in saved_handlers:
            if handler not in root_logger.handlers:
                root_logger.addHandler(handler)


def test_should_serve_spa_index_when_root_requested(static_app):
    client = TestClient(static_app.app)

    response = client.get("/")

    assert response.status_code == 200
    assert response.text == "<html>linguard-spa</html>"


def test_should_fall_back_to_index_when_frontend_route_is_unknown(static_app):
    client = TestClient(static_app.app)

    response = client.get("/servers/3/details")

    assert response.status_code == 200
    assert response.text == "<html>linguard-spa</html>"


def test_should_serve_real_files_when_they_exist_in_the_build(static_app):
    client = TestClient(static_app.app)

    favicon = client.get("/favicon.ico")
    asset = client.get("/assets/app.js")

    assert favicon.status_code == 200
    assert favicon.text == "icon-bytes"
    assert asset.status_code == 200
    assert "linguard" in asset.text


def test_should_not_shadow_api_routes_when_static_files_mounted(static_app):
    client = TestClient(static_app.app)

    response = client.get("/api/v1/does-not-exist")

    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}


def test_should_exclude_reserved_prefixes_from_spa_catch_all(static_app):
    import re

    convertor = static_app._NonReservedPath()

    for reserved in ("api/v1/servers", "docs", "redoc", "openapi.json", "health", "ws"):
        assert not re.match(convertor.regex, reserved), reserved
    for app_route in ("servers", "settings/global", ""):
        assert re.match(convertor.regex, app_route), app_route
    assert convertor.convert("servers/3") == "servers/3"
    assert convertor.to_string(7) == "7"
