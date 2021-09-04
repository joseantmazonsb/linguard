from logging import debug

from yamlable import YamlAble


class BaseConfig(YamlAble):

    def load_defaults(self):
        debug(f"Loading default settings for {self.__class__.__name__}...")
        pass

    def apply(self):
        debug(f"Applying {self.__class__.__name__}...")
        pass
