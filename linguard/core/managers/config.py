import os
from logging import info, warning, error

import yaml

from linguard.common.models.user import UserDict, users
from linguard.common.utils.logs import log_exception
from linguard.common.utils.system import try_makedir
from linguard.core.config.logger import config as logger_config
from linguard.core.config.traffic import config as traffic_config
from linguard.core.config.web import config as web_config
from linguard.core.config.wireguard import config as wireguard_config


class ConfigManager:

    def __init__(self):
        self.config_filepath = None

    def load(self, config_filepath: str):
        try:
            self.config_filepath = os.path.abspath(config_filepath)
            self.__load_config__()
            self.save(apply=False)
        except Exception as e:
            log_exception(e, is_fatal=True)
            exit(1)

    @staticmethod
    def load_defaults():
        logger_config.load_defaults()
        web_config.load_defaults()
        wireguard_config.load_defaults()
        traffic_config.load_defaults()

    def __load_config__(self):
        info(f"Restoring configuration from {self.config_filepath}...")
        if not os.path.exists(self.config_filepath):
            warning(f"Unable to restore configuration file {self.config_filepath}: not found.")
            info("Using default configuration...")
            return
        with open(self.config_filepath, "r") as file:
            config = list(yaml.safe_load_all(file))[0]
        if "logger" in config:
            logger_config.load(config["logger"])
            logger_config.apply()
        if "web" in config:
            web_config.load(config["web"])
            web_config.apply()
        if os.path.exists(web_config.credentials_file) and os.path.getsize(web_config.credentials_file) > 0:
            try:
                credentials = UserDict.load(web_config.credentials_file, web_config.secret_key)
                users.set_contents(credentials)
            except Exception:
                error(f"Invalid credentials file detected: {web_config.credentials_file}")
                raise
        if "wireguard" in config:
            wireguard_config.load(config["wireguard"])
            wireguard_config.apply()
        if "traffic" in config:
            traffic_config.load(config["traffic"])
            traffic_config.apply()
        info(f"Configuration restored!")

    def save(self, apply: bool = True):
        info("Saving configuration...")
        config = {
            "logger": logger_config,
            "web": web_config,
            "wireguard": wireguard_config,
            "traffic": traffic_config,
        }
        try_makedir(os.path.dirname(self.config_filepath))
        with open(self.config_filepath, "w") as file:
            yaml.safe_dump(config, file)
        info("Configuration saved!")
        if not apply:
            return
        logger_config.apply()
        wireguard_config.apply()
        web_config.apply()
        traffic_config.apply()

    @staticmethod
    def save_credentials():
        users.save(web_config.credentials_file, web_config.secret_key)


config_manager = ConfigManager()
