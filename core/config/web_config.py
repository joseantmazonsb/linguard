import os
import shutil
from typing import Any, Dict, Type

from yamlable import yaml_info, Y

from core.config.base_config import BaseConfig
from core.crypto_utils import CryptoUtils
from core.exceptions import WireguardError
from web.models import users
from web.utils import get_network_adapters


@yaml_info(yaml_tag='web')
class WebConfig(BaseConfig):
    MAX_PORT = 65535
    MIN_PORT = 1
    DEFAULT_HOST = "0.0.0.0"
    DEFAULT_BINDPORT = 8080
    DEFAULT_LOGIN_ATTEMPTS = 0
    __DEFAULT_CREDENTIALS_FILENAME = "credentials.yaml"

    bindport: int
    login_attempts: int
    __secret_key: str
    __credentials_file: str

    @property
    def secret_key(self):
        return self.__secret_key

    @secret_key.setter
    def secret_key(self, value: str):
        self.__secret_key = value

    @property
    def credentials_file(self):
        return self.__credentials_file

    @credentials_file.setter
    def credentials_file(self, value: str):
        old_file = self.__credentials_file
        if old_file == value:
            return
        if os.path.exists(old_file):
            shutil.copy(old_file, value)
            os.remove(old_file)
        self.__credentials_file = value

    def __init__(self):
        super().__init__()
        self.host = self.DEFAULT_HOST
        self.bindport = self.DEFAULT_BINDPORT
        self.login_attempts = self.DEFAULT_LOGIN_ATTEMPTS
        self.__secret_key = CryptoUtils.generate_key()
        self.__credentials_file = os.path.abspath(self.__DEFAULT_CREDENTIALS_FILENAME)

    def load(self, config: "WebConfig"):
        self.host = config.host or self.host
        if self.host not in get_network_adapters().keys():
            raise WireguardError(f"Invalid host: {self.host}")
        self.bindport = config.bindport or self.bindport
        self.login_attempts = config.login_attempts or self.login_attempts
        self.secret_key = config.secret_key or self.secret_key
        if config.credentials_file:
            self.credentials_file = os.path.abspath(config.credentials_file)

    def __to_yaml_dict__(self):  # type: (...) -> Dict[str, Any]
        return {
            "host": self.host,
            "bindport": self.bindport,
            "login_attempts": self.login_attempts,
            "secret_key": self.secret_key,
            "credentials_file": self.credentials_file
        }

    @classmethod
    def __from_yaml_dict__(cls,  # type: Type[Y]
                           dct,  # type: Dict[str, Any]
                           yaml_tag=""
                           ):  # type: (...) -> Y
        config = WebConfig()
        config.host = dct.get("host", None) or config.host
        config.bindport = dct.get("bindport", None) or config.bindport
        config.login_attempts = dct.get("login_attempts", None) or config.login_attempts
        config.secret_key = dct.get("secret_key", None) or config.secret_key
        config.credentials_file = dct.get("credentials_file", None) or config.credentials_file
        if config.credentials_file:
            config.credentials_file = os.path.abspath(config.credentials_file)
        return config

    def apply(self):
        super(WebConfig, self).apply()
        if not self.credentials_file or len(users) < 1:
            return
        os.remove(self.credentials_file)
        users.save(self.credentials_file, self.__secret_key)


config = WebConfig()
