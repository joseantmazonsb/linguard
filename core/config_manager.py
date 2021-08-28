import os
from logging import info, warning, error

import yaml

from core.config.linguard_config import config as linguard_config
from core.config.logger_config import config as logger_config
from core.config.web_config import config as web_config
from system_utils import log_exception
from web.models import UserDict, users


class ConfigManager:

    def __init__(self):
        self.started = False
        self.config_filepath = None

    def load(self, config_filepath: str):
        try:
            self.config_filepath = config_filepath
            self.__load_config__()
            self.save(apply=False)
        except Exception as e:
            log_exception(e, is_fatal=True)
            exit(1)

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
        if "linguard" in config:
            linguard_config.load(config["linguard"])
            linguard_config.apply()
        info(f"Configuration restored!")

    def save(self, apply: bool = True):
        info("Saving configuration...")
        config = {
            "logger": logger_config,
            "web": web_config,
            "linguard": linguard_config
        }
        with open(self.config_filepath, "w") as file:
            yaml.safe_dump(config, file)
        info("Configuration saved!")
        if not apply:
            return
        logger_config.apply()
        linguard_config.apply()
        web_config.apply()


config_manager = ConfigManager()