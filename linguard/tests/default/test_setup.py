import os

import pytest

from linguard.common.properties import global_properties
from linguard.tests.utils import default_cleanup, is_http_success, login, get_testing_app

url = "/setup"


@pytest.fixture(autouse=True)
def cleanup():
    yield
    default_cleanup()


@pytest.fixture
def client():
    with get_testing_app().test_client() as client:
        global_properties.setup_required = True
        yield client


def test_get(client):
    login(client)
    response = client.get(url)
    assert is_http_success(response.status_code)
    assert "Setup".encode() in response.data


def test_redirect(client):
    login(client)
    response = client.get("/dashboard")
    assert is_http_success(response.status_code)
    assert response.status_code == 302
    assert "/setup".encode() in response.data


def remove_setup_file():
    from linguard.web.router import setup_filepath
    os.remove(setup_filepath)


def test_post_ok(client):
    login(client)
    response = client.post(url, data={
        "app_endpoint": "vpn.example.com", "app_iptables_bin": "/usr/sbin/iptables", "app_wg_bin": "/usr/bin/wg",
        "app_wg_quick_bin": "/usr/bin/wg-quick", "log_overwrite": False, "traffic_enabled": True
    })
    assert is_http_success(response.status_code)
    assert "Setup".encode() not in response.data

    remove_setup_file()

    response = client.post(url, data={
        "app_endpoint": "10.0.0.1", "app_iptables_bin": "/usr/sbin/iptables", "app_wg_bin": "/usr/bin/wg",
        "app_wg_quick_bin": "/usr/bin/wg-quick", "log_overwrite": False, "traffic_enabled": True
    })
    assert is_http_success(response.status_code)
    assert "Setup".encode() not in response.data


def test_post_ko(client):
    login(client)

    response = client.post(url, data={
        "app_endpoint": "", "app_iptables_bin": "/usr/sbin/iptables", "app_wg_bin": "/usr/bin/wg",
        "app_wg_quick_bin": "/usr/bin/wg-quick", "log_overwrite": False, "traffic_enabled": True
    })
    assert is_http_success(response.status_code)
    assert "Setup".encode() in response.data

    response = client.post(url, data={
        "app_endpoint": 100, "app_iptables_bin": "/usr/sbin/iptables", "app_wg_bin": "/usr/bin/wg",
        "app_wg_quick_bin": "/usr/bin/wg-quick", "log_overwrite": False, "traffic_enabled": True
    })
    assert is_http_success(response.status_code)
    assert "Setup".encode() in response.data

    response = client.post(url, data={
        "app_endpoint": "vpn.example.com", "app_iptables_bin": "/usr/sbin/iptabless", "app_wg_bin": "/usr/bin/wg",
        "app_wg_quick_bin": "/usr/bin/wg-quick", "log_overwrite": False, "traffic_enabled": True
    })
    assert is_http_success(response.status_code)
    assert "Setup".encode() in response.data

    response = client.post(url, data={
        "app_endpoint": "vpn.example.com", "app_iptables_bin": "/usr/sbin/iptables", "app_wg_bin": "/usr/bin/wgg",
        "app_wg_quick_bin": "/usr/bin/wg-quick", "log_overwrite": False, "traffic_enabled": True
    })
    assert is_http_success(response.status_code)
    assert "Setup".encode() in response.data

    response = client.post(url, data={
        "app_endpoint": "vpn.example.com", "app_iptables_bin": "/usr/sbin/iptables", "app_wg_bin": "/usr/bin/wg",
        "app_wg_quick_bin": "/usr/bin/wg-quickk", "log_overwrite": False, "traffic_enabled": True
    })
    assert is_http_success(response.status_code)
    assert "Setup".encode() in response.data

    response = client.post(url, data={
        "app_endpoint": "vpn.example.com", "app_iptables_bin": "", "app_wg_bin": "/usr/bin/wg",
        "app_wg_quick_bin": "/usr/bin/wg-quick", "log_overwrite": False, "traffic_enabled": True
    })
    assert is_http_success(response.status_code)
    assert "Setup".encode() in response.data

    response = client.post(url, data={
        "app_endpoint": "vpn.example.com", "app_iptables_bin": "/usr/sbin/iptables", "app_wg_bin": "",
        "app_wg_quick_bin": "/usr/bin/wg-quick", "log_overwrite": False, "traffic_enabled": True
    })
    assert is_http_success(response.status_code)
    assert "Setup".encode() in response.data

    response = client.post(url, data={
        "app_endpoint": "vpn.example.com", "app_iptables_bin": "/usr/sbin/iptables", "app_wg_bin": "/usr/bin/wg",
        "app_wg_quick_bin": "", "log_overwrite": False, "traffic_enabled": True
    })
    assert is_http_success(response.status_code)
    assert "Setup".encode() in response.data

    response = client.post(url, data={
        "app_endpoint": 1, "app_iptables_bin": "/usr/sbin/iptables", "app_wg_bin": "/usr/bin/wg",
        "app_wg_quick_bin": "", "log_overwrite": False, "traffic_enabled": True
    })
    assert is_http_success(response.status_code)
    assert "Setup".encode() in response.data

    response = client.post(url, data={
        "app_endpoint": "vpn.example.com", "app_iptables_bin": 1231, "app_wg_bin": "/usr/bin/wg",
        "app_wg_quick_bin": "", "log_overwrite": False, "traffic_enabled": True
    })
    assert is_http_success(response.status_code)
    assert "Setup".encode() in response.data
