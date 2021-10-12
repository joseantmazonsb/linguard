import json
from datetime import datetime
from typing import Dict, Any, Type

from yamlable import YamlAble, Y

from linguard.core.models import interfaces
from linguard.core.utils.tools import run_tool


# Wireguard treats tx data as data sent by the server and rx data as data received by the server.
# Since we're taking the client approach, which is, how much data the client is receiving or
# transmitting, we need to invert the rx and tx values wireguard provides when assigning them to
# peers, but we will maintain them for interfaces. For instance, if a peer downloads a 2GB file,
# wireguard will say that the interface transmitted (tx) 2GB, and that is correct for the interface,
# but for the peer it would mean that it received (rx) 2GB. To sum up: what the peer is receiving is
# what the interface is transmitting, and the other way around.


class TrafficData:

    def __init__(self, rx_bytes: int, tx_bytes: int, last_handshake: datetime = None):
        self.rx = rx_bytes
        self.tx = tx_bytes
        self.last_handshake = last_handshake


class TrafficStorageDriver(YamlAble):

    DEFAULT_TIMESTAMP_FORMAT = "%d/%m/%Y %H:%M:%S"

    def __init__(self, timestamp_format: str = DEFAULT_TIMESTAMP_FORMAT):
        self.timestamp_format = timestamp_format

    @classmethod
    def get_name(cls) -> str:
        pass

    @staticmethod
    def get_session_data() -> Dict[str, TrafficData]:
        """
        Get traffic data of current session. This will only retrieve data from running interfaces and since the last
        time they were started.

        :return: A dictionary containing traffic data of peers and interfaces, indexed by their names.
        """
        dct = {}
        json_data = run_tool("wg-json").output
        data = json.loads(json_data)
        for iface in interfaces.values():
            if iface.name not in data:
                continue
            iface_rx = 0
            iface_tx = 0
            for peer in iface.peers.values():
                if peer.public_key not in data[iface.name]["peers"]:
                    continue
                peer_data = data[iface.name]["peers"][peer.public_key]
                peer_rx = 0
                peer_tx = 0
                if "transferRx" in peer_data:
                    peer_tx = int(peer_data["transferRx"])
                if "transferTx" in peer_data:
                    peer_rx = int(peer_data["transferTx"])
                last_handshake = None
                if "latestHandshake" in peer_data:
                    last_handshake = datetime.fromtimestamp(int(peer_data["latestHandshake"]))
                iface_tx += peer_rx
                iface_rx += peer_tx
                dct[peer.uuid] = TrafficData(peer_rx, peer_tx, last_handshake)
            dct[iface.uuid] = TrafficData(iface_rx, iface_tx)
        return dct

    def get_session_and_stored_data(self) -> Dict[datetime, Dict[str, TrafficData]]:
        """
        Get the stored traffic data and merge it with the current session's data.

        :return:
        """
        stored_traffic = self.load_data()
        session_traffic = self.get_session_data()
        if len(stored_traffic) > 0:
            for device, traffic in session_traffic.items():
                # Look for last registered data of device
                for data in reversed(list(stored_traffic.values())):
                    if device in data:
                        traffic.rx += data[device].rx
                        traffic.tx += data[device].tx
                        break
        if len(session_traffic) > 0:
            stored_traffic[datetime.now()] = session_traffic
        return stored_traffic

    def save_data(self):
        """
        Save updated traffic data.

        :return:
        """
        pass

    def load_data(self) -> Dict[datetime, Dict[str, TrafficData]]:
        """
        Get stored traffic data of all devices.

        :return: A dictionary containing traffic data of interfaces and peers, indexed by timestamp.
        """
        pass

    def __to_yaml_dict__(self):  # type: (...) -> Dict[str, Any]
        return {
            "timestamp_format": self.timestamp_format
        }

    @classmethod
    def __from_yaml_dict__(cls,      # type: Type[Y]
                           dct,      # type: Dict[str, Any]
                           yaml_tag=""
                           ):  # type: (...) -> Y
        return TrafficStorageDriver(dct.get("timestamp_format", None))
