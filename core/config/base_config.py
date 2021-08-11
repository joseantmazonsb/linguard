from logging import debug

from yamlable import YamlAble


class BaseConfig(YamlAble):

    def apply(self):
        debug(f"Applying {self.__class__.__name__}...")
        pass
