from typing import Any, Dict, Type

from yamlable import yaml_info, Y

from linguard.common.models.user import users
from linguard.common.properties import global_properties
from linguard.common.utils.encryption import CryptoUtils
from linguard.core.config.base import BaseConfig


@yaml_info(yaml_tag='web')
class WebConfig(BaseConfig):
    MAX_PORT = 65535
    MIN_PORT = 1
    DEFAULT_LOGIN_ATTEMPTS = 0
    DEFAULT_BAN_SECONDS = 120
    CREDENTIALS_FILENAME = ".credentials"

    __secret_key: str
    login_attempts: int
    login_ban_time: int

    @property
    def secret_key(self):
        return self.__secret_key

    @secret_key.setter
    def secret_key(self, value: str):
        self.__secret_key = value

    @property
    def credentials_file(self):
        return global_properties.join_workdir(self.CREDENTIALS_FILENAME)

    def __init__(self):
        super().__init__()
        self.load_defaults()

    def load_defaults(self):
        self.login_attempts = self.DEFAULT_LOGIN_ATTEMPTS
        self.login_ban_time = self.DEFAULT_BAN_SECONDS
        self.__secret_key = CryptoUtils.generate_key()

    def load(self, config: "WebConfig"):
        self.login_attempts = config.login_attempts or self.login_attempts
        self.secret_key = config.secret_key or self.secret_key

    def __to_yaml_dict__(self):  # type: (...) -> Dict[str, Any]
        return {
            "login_attempts": self.login_attempts,
            "login_ban_time": self.login_ban_time,
            "secret_key": self.secret_key
        }

    @classmethod
    def __from_yaml_dict__(cls,  # type: Type[Y]
                           dct,  # type: Dict[str, Any]
                           yaml_tag=""
                           ):  # type: (...) -> Y
        config = WebConfig()
        config.login_attempts = dct.get("login_attempts", None) or config.login_attempts
        config.login_ban_time = dct.get("login_ban_time", None) or config.login_ban_time
        config.secret_key = dct.get("secret_key", None) or config.secret_key
        return config

    def apply(self):
        super(WebConfig, self).apply()
        if not self.credentials_file or len(users) < 1:
            return
        users.save(self.credentials_file, self.__secret_key)


config = WebConfig()
