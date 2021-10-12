import pytest

from linguard.common.utils.encryption import CryptoUtils
from linguard.tests.utils import default_cleanup, is_http_success, login, get_testing_app

url = "/settings"


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
    assert "Settings".encode() in response.data


def test_post_ok(client):
    login(client)
    response = client.post(url, data={
        "app_endpoint": "vpn.example.com", "app_iptables_bin": "/usr/sbin/iptables", "app_wg_bin": "/usr/bin/wg",
        "app_wg_quick_bin": "/usr/bin/wg-quick", "web_login_attempts": 0, "web_secret_key": CryptoUtils.generate_key(),
        "log_overwrite": False, "log_level": "debug", "traffic_enabled": True, "traffic_driver": "JSON",
        "traffic_driver_options": "{}"
    })
    assert is_http_success(response.status_code)
    assert "Error".encode() not in response.data

    response = client.post(url, data={
        "app_endpoint": "10.0.0.1", "app_iptables_bin": "/usr/sbin/iptables", "app_wg_bin": "/usr/bin/wg",
        "app_wg_quick_bin": "/usr/bin/wg-quick", "web_login_attempts": 0, "web_secret_key": CryptoUtils.generate_key(),
        "log_overwrite": False, "log_level": "debug", "traffic_enabled": True, "traffic_driver": "JSON",
        "traffic_driver_options": "{}"
    })
    assert is_http_success(response.status_code)
    assert "Error".encode() not in response.data


def test_post_ko(client):
    login(client)
    response = client.post(url, data={
        "app_endpoint": 1, "app_iptables_bin": "/usr/sbin/iptables", "app_wg_bin": "/usr/bin/wg",
        "app_wg_quick_bin": "/usr/bin/wg-quick", "web_login_attempts": 0, "web_secret_key": CryptoUtils.generate_key(),
        "log_overwrite": False, "log_level": "debug", "traffic_enabled": True, "traffic_driver": "JSON",
        "traffic_driver_options": "{}"
    })
    assert is_http_success(response.status_code)
    assert "Error".encode() in response.data

    response = client.post(url, data={
        "app_endpoint": "", "app_iptables_bin": "/usr/sbin/iptabless", "app_wg_bin": "/usr/bin/wg",
        "app_wg_quick_bin": "/usr/bin/wg-quick", "web_login_attempts": 0, "web_secret_key": CryptoUtils.generate_key(),
        "log_overwrite": False, "log_level": "debug", "traffic_enabled": True, "traffic_driver": "JSON",
        "traffic_driver_options": "{}"
    })
    assert is_http_success(response.status_code)
    assert "Error".encode() in response.data

    response = client.post(url, data={
        "app_endpoint": "", "app_iptables_bin": "/usr/sbin/iptables", "app_wg_bin": "/usr/bin/wgg",
        "app_wg_quick_bin": "/usr/bin/wg-quick", "web_login_attempts": 0, "web_secret_key": CryptoUtils.generate_key(),
        "log_overwrite": False, "log_level": "debug", "traffic_enabled": True, "traffic_driver": "JSON",
        "traffic_driver_options": "{}"
    })
    assert is_http_success(response.status_code)
    assert "Error".encode() in response.data

    response = client.post(url, data={
        "app_endpoint": "", "app_iptables_bin": "/usr/sbin/iptables", "app_wg_bin": "/usr/bin/wg",
        "app_wg_quick_bin": "/usr/bin/wg-quickk", "web_login_attempts": 0, "web_secret_key": CryptoUtils.generate_key(),
        "log_overwrite": False, "log_level": "debug", "traffic_enabled": True, "traffic_driver": "JSON",
        "traffic_driver_options": "{}"
    })
    assert is_http_success(response.status_code)
    assert "Error".encode() in response.data
    
    response = client.post(url, data={
        "app_endpoint": "", "app_iptables_bin": "/usr/sbin/iptables", "app_wg_bin": "/usr/bin/wg",
        "app_wg_quick_bin": "/usr/bin/wg-quick", "web_login_attempts": "", "web_secret_key": CryptoUtils.generate_key(),
        "log_overwrite": False, "log_level": "debug", "traffic_enabled": True, "traffic_driver": "JSON",
        "traffic_driver_options": "{}"
    })
    assert is_http_success(response.status_code)
    assert "Error".encode() in response.data
    
    response = client.post(url, data={
        "app_endpoint": "", "app_iptables_bin": "/usr/sbin/iptables", "app_wg_bin": "/usr/bin/wg",
        "app_wg_quick_bin": "/usr/bin/wg-quick", "web_login_attempts": "a",
        "web_secret_key": CryptoUtils.generate_key(), "log_overwrite": False, "log_level": "debug",
        "traffic_enabled": True, "traffic_driver": "JSON", "traffic_driver_options": "{}"
    })
    assert is_http_success(response.status_code)
    assert "Error".encode() in response.data
    
    response = client.post(url, data={
        "app_endpoint": "", "app_iptables_bin": "/usr/sbin/iptables", "app_wg_bin": "/usr/bin/wg",
        "app_wg_quick_bin": "/usr/bin/wg-quick", "web_login_attempts": 0, "web_secret_key": "",
        "log_overwrite": False, "log_level": "debug", "traffic_enabled": True, "traffic_driver": "JSON",
        "traffic_driver_options": "{}"
    })
    assert is_http_success(response.status_code)
    assert "Error".encode() in response.data
    
    response = client.post(url, data={
        "app_endpoint": "", "app_iptables_bin": "/usr/sbin/iptables", "app_wg_bin": "/usr/bin/wg",
        "app_wg_quick_bin": "/usr/bin/wg-quick", "web_login_attempts": 0, "web_secret_key": "aaaaaaaaaaaaaa31a",
        "log_overwrite": False, "log_level": "debug", "traffic_enabled": True, "traffic_driver": "JSON",
        "traffic_driver_options": "{}"
    })
    assert is_http_success(response.status_code)
    assert "Error".encode() in response.data
    
    response = client.post(url, data={
        "app_endpoint": "", "app_iptables_bin": "/usr/sbin/iptables", "app_wg_bin": "/usr/bin/wg",
        "app_wg_quick_bin": "/usr/bin/wg-quick", "web_login_attempts": 0, "web_secret_key": CryptoUtils.generate_key(),
        "log_overwrite": False, "log_level": "nonsense", "traffic_enabled": True, "traffic_driver": "JSON",
        "traffic_driver_options": "{}"
    })
    assert is_http_success(response.status_code)
    assert "Error".encode() in response.data
    
    response = client.post(url, data={
        "app_endpoint": "", "app_iptables_bin": "/usr/sbin/iptables", "app_wg_bin": "/usr/bin/wg",
        "app_wg_quick_bin": "/usr/bin/wg-quick", "web_login_attempts": 0, "web_secret_key": CryptoUtils.generate_key(),
        "log_overwrite": False, "log_level": "debug", "traffic_enabled": True, "traffic_driver": "NOT_EXISTS",
        "traffic_driver_options": "{}"
    })
    assert is_http_success(response.status_code)
    assert "Error".encode() in response.data
    
    response = client.post(url, data={
        "app_endpoint": "", "app_iptables_bin": "/usr/sbin/iptables", "app_wg_bin": "/usr/bin/wg",
        "app_wg_quick_bin": "/usr/bin/wg-quick", "web_login_attempts": 0, "web_secret_key": CryptoUtils.generate_key(),
        "log_overwrite": False, "log_level": "debug", "traffic_enabled": True, "traffic_driver": "JSON",
        "traffic_driver_options": ""
    })
    assert is_http_success(response.status_code)
    assert "Error".encode() in response.data
