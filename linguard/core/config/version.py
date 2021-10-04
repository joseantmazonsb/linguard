import os
from typing import Any, Dict, Type

from yamlable import yaml_info, Y, YamlAble

from linguard.core.config.base import BaseConfig


@yaml_info(yaml_tag='version')
class VersionConfig(BaseConfig):

    filepath: str

    def __init__(self):
        self.load_defaults()
        super().__init__()

    def load_defaults(self):
        self.filepath = ""

    def load(self, config: "VersionConfig"):
        if config.filepath:
            self.filepath = os.path.abspath(config.filepath)

    def __to_yaml_dict__(self):  # type: (...) -> Dict[str, Any]
        return {
            "filepath": self.filepath
        }

    @classmethod
    def __from_yaml_dict__(cls,  # type: Type[Y]
                           dct,  # type: Dict[str, Any]
                           yaml_tag=""
                           ):  # type: (...) -> Y
        config = VersionConfig()
        config.filepath = dct.get("filepath", None) or config.filepath
        return config

    def apply(self):
        super(VersionConfig, self).apply()
        if not self.filepath:
            version_info.load_defaults()
            return
        version_info.load(self.filepath)


config = VersionConfig()


@yaml_info(yaml_tag='version_info')
class VersionInfo(YamlAble):

    release: str
    commit: str

    def __init__(self):
        self.load_defaults()

    def load_defaults(self):
        self.release = ""
        self.commit = ""

    def load(self, filepath: str):
        info = self.load_yaml(filepath)
        self.release = info.release
        self.commit = info.commit

    def __to_yaml_dict__(self):  # type: (...) -> Dict[str, Any]
        return {
            "release": self.release,
            "commit": self.commit,
        }

    @classmethod
    def __from_yaml_dict__(cls,      # type: Type[Y]
                           dct,      # type: Dict[str, Any]
                           yaml_tag  # type: str
                           ):  # type: (...) -> Y
        info = VersionInfo()
        info.release = dct.get("release", None) or info.release
        info.commit = dct.get("commit", None) or info.commit
        return info


version_info = VersionInfo()
