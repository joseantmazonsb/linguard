import pytest
from flask_login import current_user

from linguard.tests.utils import default_cleanup, is_http_success, login, exists_credentials_file, get_testing_app

url = "/profile"


@pytest.fixture(autouse=True)
def cleanup():
    yield
    default_cleanup()


@pytest.fixture
def client():
    with get_testing_app().test_client() as client:
        yield client


def test_get(client):
    login(client)

    response = client.get(url)
    assert is_http_success(response.status_code)
    assert current_user.name.encode() in response.data


def test_post_ok(client):
    login(client)

    new_username = "root"
    response = client.post(url, data={"username": new_username})
    assert is_http_success(response.status_code)
    assert b"alert-danger" not in response.data
    assert current_user.name == new_username
    assert exists_credentials_file()


def test_post_ko(client):
    login(client)

    response = client.post(url, data={"username": ""})
    assert is_http_success(response.status_code)
    assert b"alert-danger" in response.data
    assert not exists_credentials_file()
