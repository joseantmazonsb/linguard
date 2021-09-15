from yamlable import yaml_info

from linguard.core.config.base import BaseConfig
from linguard.core.drivers.traffic_storage_driver import TrafficStorageDriver
from linguard.core.drivers.traffic_storage_driver_json import TrafficStorageDriverJson


@yaml_info(yaml_tag='traffic')
class TrafficConfig(BaseConfig):
    enabled: bool
    driver: TrafficStorageDriver

    def __init__(self):
        super().__init__()
        self.load_defaults()

    def load_defaults(self):
        self.enabled = True
        self.driver = TrafficStorageDriverJson()

    def load(self, config: "TrafficConfig"):
        self.enabled = config.enabled
        self.driver = config.driver

    def __to_yaml_dict__(self):  # type: (...) -> Dict[str, Any]
        return {
            "enabled": self.enabled,
            "driver": self.driver,
        }

    @classmethod
    def __from_yaml_dict__(cls,      # type: Type[Y]
                           dct,      # type: Dict[str, Any]
                           yaml_tag=""
                           ):  # type: (...) -> Y
        config = TrafficConfig()
        enabled = config.enabled
        config.enabled = dct.get("enabled", None)
        if config.enabled is None:
            config.enabled = enabled
        config.driver = dct.get("driver", None) or config.driver
        return config


config = TrafficConfig()
