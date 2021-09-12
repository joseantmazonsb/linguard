import copy
import json
import os
from datetime import datetime
from logging import info
from typing import Dict, Any

from yamlable import yaml_info

from core.drivers.traffic_storage_driver import TrafficStorageDriver, TrafficData
from core.models import interfaces, get_all_peers


@yaml_info(yaml_tag='traffic_storage_driver_json')
class TrafficStorageDriverJson(TrafficStorageDriver):

    DEFAULT_FILEPATH = "traffic.json"

    def __init__(self, filepath: str = DEFAULT_FILEPATH,
                 timestamp_format: str = TrafficStorageDriver.DEFAULT_TIMESTAMP_FORMAT):
        super().__init__(timestamp_format)
        self.filepath = os.path.abspath(filepath)

    @classmethod
    def get_name(cls) -> str:
        return "JSON"

    def update_data(self):
        info("Updating traffic data...")
        merged_data = self.get_session_and_stored_data()
        with open(self.filepath, "w") as f:
            json_data = {}
            for timestamp, data in merged_data.items():
                device_data = {}
                for device, traffic_data in data.items():
                    if interfaces.get_value_by_attr("name", device):
                        # Do not store interface data, since it will be calculated from peers data
                        break
                    device_data[device] = {"rx": traffic_data.rx, "tx": traffic_data.tx}
                json_data[timestamp.strftime(self.timestamp_format)] = device_data
            json.dump(json_data, f)
        info("Traffic data updated.")

    def load_data(self) -> Dict[datetime, Dict[str, TrafficData]]:
        data = {}
        if not os.path.exists(self.filepath):
            return data
        with open(self.filepath, "r") as f:
            json_data = json.load(f)
        for k, v in json_data.items():
            device_data = {}
            for device, traffic_data in v.items():
                device_data[device] = TrafficData(traffic_data["rx"], traffic_data["tx"])
            data[datetime.strptime(k, self.timestamp_format)] = device_data
        # Calculate interfaces traffic data
        data_with_interfaces = copy.deepcopy(data)
        peers = get_all_peers()
        for timestamp, peer in data.items():
            for name, peer_data in peer.items():
                iface = peers.get_value_by_attr("name", name).interface
                if iface.name not in data_with_interfaces[timestamp]:
                    data_with_interfaces[timestamp][iface.name] = peer_data
                    continue
                data_with_interfaces[timestamp][iface.name].rx += peer_data.rx
                data_with_interfaces[timestamp][iface.name].tx += peer_data.tx
        return data_with_interfaces

    def __to_yaml_dict__(self):  # type: (...) -> Dict[str, Any]
        dct = super(TrafficStorageDriverJson, self).__to_yaml_dict__()
        dct["filepath"] = self.filepath
        return dct

    @classmethod
    def __from_yaml_dict__(cls,      # type: Type[Y]
                           dct,      # type: Dict[str, Any]
                           yaml_tag=""
                           ):  # type: (...) -> Y
        timestamp_format = dct.get("timestamp_format", None)
        filepath = dct.get("filepath", None)
        return TrafficStorageDriverJson(filepath, timestamp_format)
