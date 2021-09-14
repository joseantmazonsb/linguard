from typing import Any, Dict, Type

from yamlable import yaml_info, Y

from linguard.core.config.base import BaseConfig


@yaml_info(yaml_tag='version')
class VersionInfo(BaseConfig):
    optional = True

    def __init__(self):
        self.version = ""
        self.date = ""
        self.commit = ""

    def __to_yaml_dict__(self):  # type: (...) -> Dict[str, Any]
        return {
            "version": self.version,
            "date": self.date,
            "commit": self.commit,
        }

    def __from_yaml_dict__(cls,      # type: Type[Y]
                           dct,      # type: Dict[str, Any]
                           yaml_tag  # type: str
                           ):  # type: (...) -> Y
        info = VersionInfo()
        info.version = dct["version"] or info.version
        info.date = dct["date"] or info.date
        info.commit = dct["commit"] or info.commit