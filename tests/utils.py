import http
import os

from core.config.web_config import config as web_config
from core.config_manager import config_manager
from core.models import interfaces
from web.models import users


def default_cleanup():
    if os.path.exists(config_manager.config_filepath):
        os.remove(config_manager.config_filepath)
    if os.path.exists(web_config.credentials_file):
        os.remove(web_config.credentials_file)
    for iface in interfaces.values():
        iface.remove()
    users.clear()


def is_http_success(code: int):
    return code < http.HTTPStatus.BAD_REQUEST
