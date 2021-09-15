from logging import warning
from typing import Dict

from schedule import repeat, every

from linguard.core.config.traffic import config
from linguard.core.drivers.traffic_storage_driver import TrafficStorageDriver
from linguard.core.drivers.traffic_storage_driver_json import TrafficStorageDriverJson


@repeat(every(1).hours)
def __update_data__():
    if not config.enabled:
        warning("Traffic's data collection is disabled!")
        return
    config.driver.save_data()


registered_drivers: Dict[str, TrafficStorageDriver] = {}


def register_driver(driver: TrafficStorageDriver):
    name = driver.get_name()
    if name not in registered_drivers.keys():
        registered_drivers[name] = driver


def unregister_driver(name: str):
    if name in registered_drivers.keys():
        del registered_drivers[name]


register_driver(TrafficStorageDriverJson())
