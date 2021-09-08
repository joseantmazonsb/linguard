import http
import os

from flask_login import current_user

from core.config.web_config import config as web_config
from core.config_manager import config_manager
from core.models import interfaces
from web.models import users, User

username = "admin"
password = "admin"


def exists_config_file() -> bool:
    return os.path.exists(config_manager.config_filepath)


def exists_credentials_file() -> bool:
    return os.path.exists(web_config.credentials_file)


def default_cleanup():
    if exists_config_file():
        os.remove(config_manager.config_filepath)
    if exists_credentials_file():
        os.remove(web_config.credentials_file)
    for iface in interfaces.values():
        if os.path.exists(iface.conf_file):
            os.remove(iface.conf_file)
    users.clear()
    interfaces.clear()


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
    from app import app
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    return app
