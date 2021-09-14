import http
import os

from flask_login import current_user

from linguard.common.models.user import users, User
from linguard.core.config.traffic import config as traffic_config
from linguard.core.config.web import config as web_config
from linguard.core.managers.config import config_manager
from linguard.core.managers.cron import cron_manager
from linguard.core.models import interfaces

username = "admin"
password = "admin"


def exists_config_file() -> bool:
    return os.path.exists(config_manager.config_filepath)


def exists_credentials_file() -> bool:
    return os.path.exists(web_config.credentials_file)


def exists_traffic_file() -> bool:
    if not traffic_config.driver.filepath:
        return False
    return os.path.exists(traffic_config.driver.filepath)


def default_cleanup():
    if exists_config_file():
        os.remove(config_manager.config_filepath)
    if exists_credentials_file():
        os.remove(web_config.credentials_file)
    if exists_traffic_file():
        os.remove(traffic_config.driver.filepath)
    for iface in interfaces.values():
        if os.path.exists(iface.conf_file):
            os.remove(iface.conf_file)
    users.clear()
    interfaces.clear()
    cron_manager.stop()


def is_http_success(code: int):
    return code < http.HTTPStatus.BAD_REQUEST


def login(client):
    u = User(username)
    u.password = password
    users[u.id] = u

    response = client.post("/login", data={"username": username, "password": password, "remember_me": False})
    assert is_http_success(response.status_code), default_cleanup()
    assert current_user.name == "admin", default_cleanup()


def get_testing_app():
    from linguard.__main__ import app
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    return app
