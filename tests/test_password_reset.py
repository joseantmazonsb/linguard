import sys

import pytest
from flask_login import current_user

from tests.utils import default_cleanup, is_http_success
from web.models import users, User

url = "/profile/password-reset"
username = "admin"
password = "admin"


def cleanup():
    default_cleanup()


@pytest.fixture
def client():
    sys.argv = [sys.argv[0], "linguard.test.yaml"]
    from app import app
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    with app.test_client() as client:
        yield client


def login(client):
    u = User(username)
    u.password = password
    users[u.id] = u

    response = client.post("/login", data={"username": username, "password": password, "remember_me": False})
    assert is_http_success(response.status_code), cleanup()
    assert current_user.name == "admin", cleanup()


def test_get(client):
    response = client.get(url)
    assert is_http_success(response.status_code), cleanup()

    cleanup()


def test_post_ok(client):
    login(client)

    response = client.post(url, data={"old_password": password, "new_password": "1234", "confirm": "1234"})
    assert is_http_success(response.status_code), cleanup()
    assert b"alert-danger" not in response.data, cleanup()

    cleanup()


def test_post_ko(client):
    login(client)

    response = client.post(url, data={"old_password": password, "new_password": "1234", "confirm": "123"})
    assert is_http_success(response.status_code), cleanup()
    assert b"alert-danger" in response.data, cleanup()

    response = client.post(url, data={"old_password": password, "new_password": "", "confirm": ""})
    assert is_http_success(response.status_code), cleanup()
    assert b"alert-danger" in response.data, cleanup()

    response = client.post(url, data={"old_password": "root", "new_password": "1234", "confirm": "1234"})
    assert is_http_success(response.status_code), cleanup()
    assert b"alert-danger" in response.data, cleanup()

    cleanup()
