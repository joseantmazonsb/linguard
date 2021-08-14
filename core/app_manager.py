import os
from collections import OrderedDict
from http.client import BAD_REQUEST
from logging import info, warning, error
from time import sleep
from typing import Union, List, Dict

import yaml

from core.config.linguard_config import config as linguard_config
from core.config.logger_config import config as logger_config
from core.config.web_config import config as web_config
from core.exceptions import WireguardError
from core.models import Interface, Peer
from core.modules.interface_manager import InterfaceManager
from core.modules.key_manager import KeyManager
from core.modules.peer_manager import PeerManager
from core.utils import log_exception
from web.models import UserDict, users


class AppManager:
    pending_interfaces: Dict[str, Interface]
    pending_peers: Dict[str, Peer]

    def __init__(self):
        self.started = False
        self.key_manager = None
        self.peer_manager = None
        self.interface_manager = None
        self.config_filepath = None

    def initialize(self, config_filepath: str):
        try:
            self.config_filepath = config_filepath
            self.__load_config__()
            self.save_changes()
            self.pending_interfaces = OrderedDict()
            self.pending_peers = OrderedDict()
            self.key_manager = KeyManager(linguard_config.wg_bin)
            self.interface_manager = InterfaceManager(self.key_manager)
            self.peer_manager = PeerManager(self.key_manager)
        except Exception as e:
            log_exception(e, is_fatal=True)
            exit(1)

    def __load_config__(self):
        info(f"Restoring configuration from {self.config_filepath}...")
        if not os.path.exists(self.config_filepath):
            warning(f"Unable to restore configuration file {self.config_filepath}: not found.")
            info("Using default configuration...")
            return
        with open(self.config_filepath, "r") as file:
            config = list(yaml.safe_load_all(file))[0]
        if "logger" in config:
            logger_config.load(config["logger"])
            logger_config.apply()
        if "web" in config:
            web_config.load(config["web"])
            web_config.apply()
        if os.path.exists(web_config.credentials_file) and os.path.getsize(web_config.credentials_file) > 0:
            try:
                credentials = UserDict.load(web_config.credentials_file, web_config.secret_key)
                users.set_contents(credentials)
            except Exception:
                error(f"Invalid credentials file detected: {web_config.credentials_file}")
                raise
        if "linguard" in config:
            linguard_config.load(config["linguard"])
            linguard_config.apply()
        info(f"Configuration restored!")

    def save_changes(self):
        info("Saving configuration...")
        config = {
            "logger": logger_config,
            "web": web_config,
            "linguard": linguard_config
        }
        with open(self.config_filepath, "w") as file:
            yaml.safe_dump(config, file)
        info("Configuration saved!")
        logger_config.apply()
        linguard_config.apply()
        web_config.apply()

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

    @staticmethod
    def get_iface_by_name(name: str) -> Interface:
        for iface in linguard_config.interfaces.values():
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

    def start(self):
        info("Starting VPN server...")
        if self.started:
            warning("Unable to start VPN server: already started.")
            return
        for iface in linguard_config.interfaces.values():
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
        for iface in linguard_config.interfaces.values():
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


manager = AppManager()
