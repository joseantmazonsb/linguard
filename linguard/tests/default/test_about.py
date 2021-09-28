import pytest

from linguard.core.config.version import version_info
from linguard.core.managers.config import GLOBAL_PROPERTIES
from linguard.tests.default.utils import get_default_app
from linguard.tests.utils import default_cleanup, is_http_success, login

url = "/about"


@pytest.fixture(autouse=True)
def cleanup():
    yield
    default_cleanup()


@pytest.fixture
def client():
    with get_default_app().test_client() as client:
        yield client


class TestAbout:

    def test_get(self, client):
        login(client)
        commit = "1234567890"
        release = "0.1.0"
        version_info.commit = commit
        version_info.release = release
        response = client.get(url)
        assert is_http_success(response.status_code)
        assert release.encode() in response.data
        assert commit.encode() in response.data

    def test_get_no_version(self, client):
        login(client)
        commit = "1234567890"
        release = "0.1.0"
        response = client.get(url)
        assert is_http_success(response.status_code)
        assert release.encode() not in response.data
        assert commit.encode() not in response.data

    def test_get_version_info_in_footer_prod(self, client):
        login(client)
        commit = "1234567890"
        release = "0.1.0"
        version_info.commit = commit
        version_info.release = release
        response = client.get("/dashboard")
        assert is_http_success(response.status_code)
        assert release.encode() in response.data
        assert commit[:7].encode() not in response.data

    def test_get_version_info_in_footer_dev(self, client):
        login(client)
        commit = "1234567890"
        release = "0.1.0"
        version_info.commit = commit
        version_info.release = release
        GLOBAL_PROPERTIES["dev_env"] = True
        response = client.get("/dashboard")
        assert is_http_success(response.status_code)
        assert release.encode() in response.data
        assert commit[:7].encode() in response.data
