import os
import sys
from time import sleep

import pytest
from flask_login import current_user

from core.config.web_config import config as web_config
from core.config_manager import config_manager
from core.wireguard_manager import wireguard_manager
from tests.utils import default_cleanup, is_http_success
from web.models import users, User


class TestDefaultOptions:
    """Test using default options and default app."""

    @staticmethod
    def cleanup():
        default_cleanup()
        config_manager.load_defaults()

    @pytest.fixture
    def client(self):
        sys.argv = [sys.argv[0], "linguard.test.yaml"]
        from app import app
        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = False
        with app.test_client() as client:
            yield client

    def test_signup_ok(self, client):
        response = client.post("/signup", data={"username": "admin", "password": "admin", "confirm": "admin"},
                               follow_redirects=True)
        assert is_http_success(response.status_code), self.cleanup()
        assert os.path.exists(web_config.credentials_file), self.cleanup()
        assert current_user.name == "admin", self.cleanup()
        self.cleanup()

    def test_signup_ko(self, client):
        response = client.post("/signup", data={"username": "admin", "password": "admin"},
                               follow_redirects=True)
        assert is_http_success(response.status_code), self.cleanup()
        assert not os.path.exists(web_config.credentials_file), self.cleanup()
        assert not current_user.is_authenticated, self.cleanup()
        self.cleanup()

    def test_login_logout_ok(self, client):
        admin_user = User("admin")
        admin_user.password = "admin"
        users[admin_user.id] = admin_user
        users.save(web_config.credentials_file, web_config.secret_key)

        response = client.post("/login", data={"username": "admin", "password": "admin", "remember_me": False})
        assert is_http_success(response.status_code), self.cleanup()
        assert current_user.name == "admin", self.cleanup()

        response = client.get("/logout")
        assert is_http_success(response.status_code), self.cleanup()
        assert not current_user.is_authenticated, self.cleanup()

        self.cleanup()

    def test_login_ko(self, client):
        admin_user = User("admin")
        admin_user.password = "admin"
        users[admin_user.id] = admin_user
        users.save(web_config.credentials_file, web_config.secret_key)

        response = client.post("/login", data={"username": "admin", "password": "1234", "remember_me": False})
        assert is_http_success(response.status_code), self.cleanup()
        assert not current_user.is_authenticated, self.cleanup()

        self.cleanup()


class TestWireguardManager:

    @staticmethod
    def cleanup():
        default_cleanup()

    def test_default_server(self):
        """Test with not existent configuration file, so that the app loads all default values."""
        config_manager.load("linguard.test.yaml")
        wireguard_manager.start()
        sleep(1)
        wireguard_manager.stop()
        self.cleanup()

    @pytest.mark.skipif("skip_sample_server" in os.environ, reason="This test may fail due to permission issues.")
    def test_sample_server(self):
        path = "../config/linguard.sample.yaml"
        if "github_action_hook" in os.environ:
            path = "config/linguard.sample.yaml"
        config_manager.load(path)
        wireguard_manager.start()
        sleep(1)
        wireguard_manager.stop()
