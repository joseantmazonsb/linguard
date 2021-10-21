from time import sleep

import pytest
from flask_login import current_user

from linguard.common.models.user import User, users
from linguard.core.config.web import config
from linguard.tests.utils import default_cleanup, is_http_success, username, password, get_testing_app
from linguard.web.client import clients

url = "/login"


@pytest.fixture(autouse=True)
def cleanup():
    yield
    default_cleanup()
    config.login_attempts = 0
    config.login_ban_time = config.DEFAULT_BAN_SECONDS


@pytest.fixture
def client():
    with get_testing_app().test_client() as client:
        yield client


@pytest.fixture(autouse=True)
def setup():
    u = User(username)
    u.password = password
    users[u.id] = u


def test_post_ok(client):
    response = client.post(url, data={"username": username, "password": password, "remember_me": False},
                           follow_redirects=True)
    assert is_http_success(response.status_code)
    assert current_user.is_authenticated
    assert current_user.name == "admin"
    assert b"Dashboard" in response.data


def test_post_ko(client):
    response = client.post(url, data={"username": username + "a", "password": password, "remember_me": False},
                           follow_redirects=True)
    assert is_http_success(response.status_code)
    assert not current_user.is_authenticated
    assert b"Dashboard" not in response.data

    response = client.post(url, data={"username": username, "password": password + "b", "remember_me": False},
                           follow_redirects=True)
    assert is_http_success(response.status_code)
    assert not current_user.is_authenticated
    assert b"Dashboard" not in response.data

    response = client.post(url, data={"username": username + "a", "password": password + "b", "remember_me": False},
                           follow_redirects=True)
    assert is_http_success(response.status_code)
    assert not current_user.is_authenticated
    assert b"Dashboard" not in response.data


def test_ban_time(client):
    config.login_attempts = 1
    config.login_ban_time = 2

    response = client.post(url, data={"username": username + "a", "password": password, "remember_me": False},
                           follow_redirects=True)
    assert is_http_success(response.status_code)
    assert not current_user.is_authenticated
    assert b"Dashboard" not in response.data

    response = client.post(url, data={"username": username + "a", "password": password, "remember_me": False},
                           follow_redirects=True)
    assert is_http_success(response.status_code)
    assert not current_user.is_authenticated
    assert b"Dashboard" not in response.data
    assert f"try again in <code>{config.login_ban_time}</code> seconds".encode() in response.data or \
        f"try again in <code>{config.login_ban_time - 1}</code> seconds".encode() in response.data

    sleep(config.login_ban_time)

    response = client.post(url, data={"username": username, "password": password, "remember_me": False},
                           follow_redirects=True)
    assert is_http_success(response.status_code)
    assert current_user.is_authenticated
    assert b"Dashboard" in response.data


def test_ban_by_ip(client):
    config.login_attempts = 1
    config.login_ban_time = 10

    response = client.post(url, data={"username": username + "a", "password": password, "remember_me": False},
                           follow_redirects=True)
    assert is_http_success(response.status_code)
    assert not current_user.is_authenticated
    assert b"Dashboard" not in response.data

    response = client.post(url, data={"username": username + "a", "password": password, "remember_me": False},
                           follow_redirects=True)

    assert is_http_success(response.status_code)
    assert not current_user.is_authenticated
    assert b"Dashboard" not in response.data
    assert f"try again in <code>{config.login_ban_time}</code> seconds".encode() in response.data or \
           f"try again in <code>{config.login_ban_time - 1}</code> seconds".encode() in response.data

    clients.clear()

    response = client.post(url, data={"username": username, "password": password, "remember_me": False},
                           follow_redirects=True)
    assert is_http_success(response.status_code)
    assert current_user.is_authenticated
    assert b"Dashboard" in response.data
