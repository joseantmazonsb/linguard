from http.client import BAD_REQUEST

from faker import Faker
from collections import OrderedDict
from time import sleep
import os
from logging import fatal, info, warning
from typing import Union, List, Dict

from core.modules.config import Config
from core.modules.interface_manager import InterfaceManager
from core.modules.key_manager import KeyManager
from core.modules.peer_manager import PeerManager
from core.exceptions import WireguardError
from core.utils import try_makedir
from core.wireguard import Peer, Interface

from web.static.assets.resources import APP_NAME

CONFIG_FILE_NAME = "config.yaml"
BACKUPS_FOLDER_NAME = "backups"
INTERFACES_FOLDER_NAME = "interfaces"

fake = Faker()


class Server:
    pending_interfaces: Dict[str, Interface]
    pending_peers: Dict[str, Peer]
    interfaces: Dict[str, Interface]
    config: Config

    def __init__(self, config_filepath: str):
        try:
            info(f"Using {config_filepath} as configuration file...")
            self.started = False
            self.config = Config(config_filepath)
            self.config.load()
            self.pending_interfaces = OrderedDict()
            self.pending_peers = OrderedDict()
            linguard_config = self.config.linguard()
            self.interfaces = linguard_config["interfaces"]
            self.key_manager = KeyManager(linguard_config["wg_bin"])
            self.interface_manager = InterfaceManager(linguard_config["interfaces"], self.key_manager,
                                                      linguard_config["interfaces_folder"], linguard_config["iptables_bin"],
                                                      linguard_config["wg_quick_bin"], linguard_config["gw_iface"], fake)
            self.peer_manager = PeerManager(linguard_config["endpoint"], self.key_manager, fake)

        except Exception as e:
            fatal(f"Unable to initialize server: {e}")
            exit(1)

    def save_changes(self):
        self.config.linguard()["interfaces"] = self.interfaces
        self.config.save()

    # Interfaces

    def is_port_in_use(self, port: int) -> bool:
        return self.interface_manager.is_port_in_use(port)

    def add_iface(self, iface: Interface):
        if iface.uuid not in self.pending_interfaces:
            raise WireguardError("Invalid interface addition!", BAD_REQUEST)
        del self.pending_interfaces[iface.uuid]
        self.interface_manager.add_iface(iface)

    def generate_interface(self) -> Interface:
        iface = self.interface_manager.generate_interface()
        self.pending_interfaces[iface.uuid] = iface
        return iface

    def remove_interface(self, iface: Union[Interface, str]):
        if not self.interface_manager.remove_interface(iface):
            return False
        for peer in iface.peers:
            self.remove_peer(peer)

    def edit_interface(self, iface: Interface, name: str, description: str, ipv4_address: str,
                       port: int, gw_iface: str, auto: bool, on_up: List[str], on_down: List[str]):
        self.interface_manager.edit_interface(iface, name, description, ipv4_address, port, gw_iface, auto, on_up,
                                              on_down)

    def regenerate_keys(self, iface: Union[Interface, str]):
        self.interface_manager.regenerate_keys(iface)

    def iface_up(self, iface: Union[Interface, str]):
        self.interface_manager.iface_up(iface)

    def iface_down(self, iface: Union[Interface, str]):
        self.interface_manager.iface_down(iface)

    def save_iface(self, iface: Union[Interface, str]):
        self.interface_manager.save_iface(iface)

    def apply_iface(self, iface: Union[Interface, str]):
        self.interface_manager.apply_iface(iface)

    def restart_iface(self, iface: Union[Interface, str]):
        self.interface_manager.restart_iface(iface)

    # peers

    def get_iface_by_name(self, name: str) -> Interface:
        for iface in self.interfaces.values():
            if iface.name == name:
                return iface
        raise WireguardError(f"unable to retrieve interface '{name}'!", BAD_REQUEST)

    def get_pending_peer_by_name(self, name: str) -> Peer:
        for peer in self.pending_peers.values():
            if peer.name == name:
                return peer
        raise WireguardError(f"Unable to retrieve pending peer '{name}'!", BAD_REQUEST)

    def generate_peer(self, interface: Interface = None) -> Peer:
        peer = self.peer_manager.generate_peer(interface)
        self.pending_peers[peer.uuid] = peer
        return peer

    def add_peer(self, peer: Peer):
        if peer.uuid not in self.pending_peers:
            raise WireguardError("Invalid peer addition!", BAD_REQUEST)
        del self.pending_peers[peer.uuid]
        self.peer_manager.add_peer(peer)

    def edit_peer(self, peer: Peer, name: str, description: str, ipv4_address: str, iface: Interface, dns1: str,
                  nat: bool, dns2: str = ""):
        self.peer_manager.edit_peer(peer, name, description, ipv4_address, iface, dns1, nat, dns2)

    def remove_peer(self, peer: Peer):
        self.peer_manager.remove_peer(peer)

    def load_config(self):
        self.config.load()

    def start(self):
        info("Starting VPN server...")
        if self.started:
            warning("Unable to start VPN server: already started.")
            return
        for iface in self.interfaces.values():
            if not iface.auto:
                continue
            try:
                iface.up()
            except WireguardError:
                pass
        self.started = True
        info("VPN server started.")

    def stop(self):
        info("Stopping VPN server...")
        if not self.started:
            warning("Unable to stop VPN server: already stopped.")
            return
        for iface in self.interfaces.values():
            try:
                iface.down()
            except WireguardError:
                pass
        self.started = False
        info("VPN server stopped.")

    def restart(self):
        self.stop()
        sleep(1)
        self.start()


if __name__ == '__main__':
    server_folder = APP_NAME.lower()
    wg = Server(server_folder)
    wg.start()
    sleep(10)
    wg.stop()
