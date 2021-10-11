import logging
from typing import Dict, Any, Type

from yamlable import yaml_info, Y

from linguard.common.properties import global_properties
from linguard.core.config.base import BaseConfig
from linguard.core.exceptions import WireguardError
from linguard.web.static.assets.resources import APP_NAME


@yaml_info(yaml_tag='logger')
class LoggerConfig(BaseConfig):
    LEVELS = {
        "debug": logging.DEBUG,
        "info": logging.INFO,
        "warning": logging.WARNING,
        "error": logging.ERROR,
        "fatal": logging.FATAL
    }
    DEFAULT_LEVEL = logging.INFO
    LOG_FORMAT = "%(asctime)s [%(levelname)s] %(module)s (%(funcName)s): %(message)s"
    LOG_FILENAME = f"{APP_NAME.lower()}.log"

    level: str
    overwrite = bool

    @property
    def logfile(self):
        return global_properties.join_workdir(self.LOG_FILENAME)

    def __init__(self):
        super().__init__()
        self.load_defaults()

    def load_defaults(self):
        self.overwrite = False
        self.level = logging.getLevelName(self.DEFAULT_LEVEL).lower()

    def load(self, config: "LoggerConfig"):
        self.level = config.level or self.level
        if self.level not in self.LEVELS:
            raise WireguardError(f"'{self.level}' is not a valid log level!")
        self.overwrite = config.overwrite

    def __to_yaml_dict__(self):  # type: (...) -> Dict[str, Any]
        return {
            "overwrite": self.overwrite,
            "level": self.level,
        }

    @classmethod
    def __from_yaml_dict__(cls,      # type: Type[Y]
                           dct,      # type: Dict[str, Any]
                           yaml_tag=""
                           ):  # type: (...) -> Y
        config = LoggerConfig()
        config.level = dct.get("level", None) or config.level
        if config.level not in config.LEVELS:
            raise WireguardError(f"'{config.level}' is not a valid log level!")
        overwrite = config.overwrite
        config.overwrite = dct.get("overwrite", None)
        if config.overwrite is None:
            config.overwrite = overwrite
        return config

    def apply(self):
        super(LoggerConfig, self).apply()
        if self.overwrite:
            filemode = "w"
        else:
            filemode = "a"
        handlers = [logging.FileHandler(self.logfile, filemode, "utf-8")]
        logging.basicConfig(format=self.LOG_FORMAT, level=self.LEVELS[self.level], handlers=handlers, force=True)


config = LoggerConfig()
logging.basicConfig(format=LoggerConfig.LOG_FORMAT, level=LoggerConfig.DEFAULT_LEVEL, force=True)
