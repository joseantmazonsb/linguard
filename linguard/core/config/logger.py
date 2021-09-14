import logging
import os
from logging import info, warning

from yamlable import yaml_info

from linguard.core.config.base import BaseConfig
from linguard.core.exceptions import WireguardError


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

    level: str
    overwrite = bool
    logfile = str

    def __init__(self):
        super().__init__()
        self.load_defaults()

    def load_defaults(self):
        self.overwrite = False
        self.level = logging.getLevelName(self.DEFAULT_LEVEL).lower()
        self.logfile = ""

    def load(self, config: "LoggerConfig"):
        self.logfile = config.logfile
        self.level = config.level or self.level
        if self.level not in self.LEVELS:
            raise WireguardError(f"'{self.level}' is not a valid log level!")
        self.overwrite = config.overwrite
        if self.logfile:
            self.logfile = os.path.abspath(self.logfile)

    def __to_yaml_dict__(self):  # type: (...) -> Dict[str, Any]
        return {
            "overwrite": self.overwrite,
            "level": self.level,
            "logfile": self.logfile
        }

    @classmethod
    def __from_yaml_dict__(cls,      # type: Type[Y]
                           dct,      # type: Dict[str, Any]
                           yaml_tag=""
                           ):  # type: (...) -> Y
        config = LoggerConfig()
        config.logfile = dct.get("logfile", None) or config.logfile
        config.level = dct.get("level", None) or config.level
        if config.level not in config.LEVELS:
            raise WireguardError(f"'{config.level}' is not a valid log level!")
        overwrite = config.overwrite
        config.overwrite = dct.get("overwrite", None)
        if config.overwrite is None:
            config.overwrite = overwrite
        if config.logfile:
            config.logfile = os.path.abspath(config.logfile)
        return config

    def apply(self):
        super(LoggerConfig, self).apply()
        if self.overwrite:
            filemode = "w"
        else:
            filemode = "a"
        if self.logfile:
            info(f"Logging to {self.logfile}...")
            handlers = [logging.FileHandler(self.logfile, filemode, "utf-8")]
        else:
            warning("No logfile specified. Logging to stdout...")
            handlers = None
        logging.basicConfig(format=self.LOG_FORMAT, level=self.LEVELS[self.level], handlers=handlers, force=True)


config = LoggerConfig()
logging.basicConfig(format=config.LOG_FORMAT, level=config.LEVELS[config.level], force=True)
