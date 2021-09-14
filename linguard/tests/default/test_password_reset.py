import pytest
from flask_login import current_user

from linguard.tests.default.test_profile import url
from linguard.tests.default.utils import get_default_app
from linguard.tests.utils import default_cleanup, is_http_success, login, password, exists_credentials_file


def cleanup():
    default_cleanup()


@pytest.fixture
def client():
    with get_default_app().test_client() as client:
        yield client


def test_post_ok(client):
    login(client)

    new_password = "1234"
    response = client.post(url, data={"old_password": password, "new_password": new_password, "confirm": new_password})
    assert is_http_success(response.status_code), cleanup()
    assert b"alert-danger" not in response.data, cleanup()
    assert current_user.check_password(new_password)
    assert exists_credentials_file()

    cleanup()


def test_post_ko(client):
    login(client)

    response = client.post(url, data={"old_password": password, "new_password": "1234", "confirm": "123"})
    assert is_http_success(response.status_code), cleanup()
    assert b"alert-danger" in response.data, cleanup()
    assert not exists_credentials_file()

    response = client.post(url, data={"old_password": password, "new_password": "", "confirm": ""})
    assert is_http_success(response.status_code), cleanup()
    assert b"alert-danger" in response.data, cleanup()
    assert not exists_credentials_file()

    response = client.post(url, data={"old_password": password, "new_password": password, "confirm": password})
    assert is_http_success(response.status_code), cleanup()
    assert b"alert-danger" in response.data, cleanup()
    assert not exists_credentials_file()

    response = client.post(url, data={"old_password": "root", "new_password": "1234", "confirm": "1234"})
    assert is_http_success(response.status_code), cleanup()
    assert b"alert-danger" in response.data, cleanup()
    assert not exists_credentials_file()

    cleanup()
