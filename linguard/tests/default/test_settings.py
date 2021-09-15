import pytest

from linguard.tests.default.utils import get_default_app
from linguard.tests.utils import default_cleanup, is_http_success, login

url = "/settings"


def cleanup():
    default_cleanup()


@pytest.fixture
def client():
    with get_default_app().test_client() as client:
        yield client


def test_get(client):
    login(client)
    response = client.get(url)
    assert is_http_success(response.status_code), cleanup()

    cleanup()
