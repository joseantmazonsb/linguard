"""Tests for DatabaseManager: URL construction, validation and driver metadata."""
import pytest

from app.utils.database_manager import DatabaseManager


class TestGetDatabaseUrl:
    def test_should_return_custom_url_verbatim(self):
        url = "postgresql+asyncpg://u:p@h:5432/db"

        assert DatabaseManager.get_database_url("sqlite", custom_url=url) == url

    def test_should_build_sqlite_url_and_create_parent_directory(self, tmp_path):
        target = tmp_path / "nested" / "dir" / "linguard.db"

        url = DatabaseManager.get_database_url("sqlite", sqlite_path=str(target))

        assert url == f"sqlite+aiosqlite:///{target}"
        assert target.parent.is_dir()

    def test_should_use_default_sqlite_path_when_none_given(self):
        url = DatabaseManager.get_database_url("sqlite")

        assert url == f"sqlite+aiosqlite:///{DatabaseManager.DEFAULT_SQLITE_PATH}"

    def test_should_read_postgres_settings_from_environment(self, monkeypatch):
        monkeypatch.setenv("POSTGRES_HOST", "pg.internal")
        monkeypatch.setenv("POSTGRES_PORT", "6543")
        monkeypatch.setenv("POSTGRES_USER", "linguard")
        monkeypatch.setenv("POSTGRES_PASSWORD", "s3cret")
        monkeypatch.setenv("POSTGRES_DB", "linguard_db")

        url = DatabaseManager.get_database_url("postgresql")

        assert url == "postgresql+asyncpg://linguard:s3cret@pg.internal:6543/linguard_db"

    def test_should_fall_back_to_postgres_defaults(self, monkeypatch):
        for name in (
            "POSTGRES_HOST", "POSTGRES_PORT", "POSTGRES_USER",
            "POSTGRES_PASSWORD", "POSTGRES_DB",
        ):
            monkeypatch.delenv(name, raising=False)

        url = DatabaseManager.get_database_url("postgresql")

        assert url == "postgresql+asyncpg://wireguard:wireguard@postgres:5432/wireguard"

    def test_should_read_mysql_settings_from_environment(self, monkeypatch):
        monkeypatch.setenv("MYSQL_HOST", "mysql.internal")
        monkeypatch.setenv("MYSQL_PORT", "3307")
        monkeypatch.setenv("MYSQL_USER", "linguard")
        monkeypatch.setenv("MYSQL_PASSWORD", "s3cret")
        monkeypatch.setenv("MYSQL_DATABASE", "linguard_db")

        url = DatabaseManager.get_database_url("mysql")

        assert url == "mysql+aiomysql://linguard:s3cret@mysql.internal:3307/linguard_db"

    def test_should_raise_for_unsupported_database_type(self):
        with pytest.raises(ValueError, match="Unsupported database type"):
            DatabaseManager.get_database_url("oracle")


class TestValidateDatabaseUrl:
    @pytest.mark.parametrize(
        "url",
        [
            "postgresql+asyncpg://u:p@h:5432/db",
            "sqlite+aiosqlite:///tmp/x.db",
            "mysql+aiomysql://u:p@h:3306/db",
        ],
    )
    def test_should_accept_supported_drivers(self, url):
        assert DatabaseManager.validate_database_url(url) is True

    @pytest.mark.parametrize(
        "url",
        [
            None,
            "",
            "sqlite:///tmp/x.db",          # sync driver
            "postgresql://u:p@h/db",        # sync driver
            "mysql+pymysql://u:p@h/db",     # sync driver
        ],
    )
    def test_should_reject_sync_or_missing_urls(self, url):
        assert DatabaseManager.validate_database_url(url) is False


class TestDriverMetadata:
    @pytest.mark.parametrize(
        ("db_type", "driver"),
        [("postgresql", "asyncpg"), ("sqlite", "aiosqlite"), ("mysql", "aiomysql")],
    )
    def test_should_report_async_driver(self, db_type, driver):
        assert DatabaseManager.get_driver_name(db_type) == driver

    def test_should_return_empty_driver_for_unknown_type(self):
        assert DatabaseManager.get_driver_name("oracle") == ""

    def test_should_list_required_packages_per_backend(self):
        assert DatabaseManager.get_required_packages("mysql") == ["aiomysql", "cryptography"]
        assert DatabaseManager.get_required_packages("sqlite") == ["aiosqlite"]
        assert DatabaseManager.get_required_packages("oracle") == []
