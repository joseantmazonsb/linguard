import os
import shutil
from os.path import dirname, join
from time import sleep

import pytest
from flask_login import current_user

from linguard.common.models.user import users, User
from linguard.common.properties import global_properties
from linguard.common.utils.system import try_makedir
from linguard.core.config.web import config as web_config
from linguard.core.managers.config import config_manager
from linguard.core.managers.wireguard import wireguard_manager
from linguard.tests.utils import default_cleanup, is_http_success, get_testing_app


@pytest.fixture(autouse=True)
def cleanup():
    yield
    default_cleanup()
    config_manager.load_defaults()


@pytest.fixture
def client():
    with get_testing_app().test_client() as client:
        yield client


def test_signup_ok(client):
    response = client.post("/signup", data={"username": "admin", "password": "admin", "confirm": "admin"},
                           follow_redirects=True)
    assert is_http_success(response.status_code)
    assert os.path.exists(web_config.credentials_file)
    assert current_user.name == "admin"


def test_signup_ko(client):
    response = client.post("/signup", data={"username": "admin", "password": "admin"},
                           follow_redirects=True)
    assert is_http_success(response.status_code)
    assert not os.path.exists(web_config.credentials_file)
    assert not current_user.is_authenticated


def test_login_logout_ok(client):
    admin_user = User("admin")
    admin_user.password = "admin"
    users[admin_user.id] = admin_user
    users.save(web_config.credentials_file, web_config.secret_key)

    response = client.post("/login", data={"username": "admin", "password": "admin", "remember_me": False})
    assert is_http_success(response.status_code)
    assert current_user.name == "admin"

    response = client.get("/logout")
    assert is_http_success(response.status_code)
    assert not current_user.is_authenticated


def test_login_ko(client):
    admin_user = User("admin")
    admin_user.password = "admin"
    users[admin_user.id] = admin_user
    users.save(web_config.credentials_file, web_config.secret_key)

    response = client.post("/login", data={"username": "admin", "password": "1234", "remember_me": False})
    assert is_http_success(response.status_code)
    assert not current_user.is_authenticated


def test_default_server():
    """Test with not existent configuration file, so that the app loads all default values."""
    workdir = join(dirname(__file__), "data")
    try_makedir(workdir)
    global_properties.workdir = workdir
    config_manager.load()
    wireguard_manager.start()
    sleep(1)
    wireguard_manager.stop()


def test_sample_server():
    workdir = join(dirname(__file__), "data")
    try_makedir(workdir)
    sample_file = join(dirname(dirname(dirname(__file__))), "config", "linguard.sample.yaml")
    shutil.copy(sample_file, workdir)
    global_properties.workdir = workdir
    config_manager.load()
    wireguard_manager.start()
    sleep(1)
    wireguard_manager.stop()
