from http.client import BAD_REQUEST

from faker import Faker
from collections import OrderedDict
from time import sleep
import os
from logging import fatal, info, debug, warning
from typing import Union, List, Dict
from urllib import request

from core.modules.config import Config
from core.modules.interface_manager import InterfaceManager
from core.modules.key_manager import KeyManager
from core.modules.peer_manager import PeerManager
from core.utils import run_os_command
from core.exceptions import WireguardError
from core.wireguard import Peer, Interface

from web.static.assets.resources import APP_NAME

CONFIG_FILE_NAME = "config.yaml"
BACKUPS_FOLDER_NAME = "backups"
INTERFACES_FOLDER_NAME = "interfaces"
IP_RETRIEVER_URL = "https://api.ipify.org"

fake = Faker()


class Server:
    pending_interfaces: Dict[str, Interface]
    pending_peers: Dict[str, Peer]
    interfaces: Dict[str, Interface]
    config = Config

    def __init__(self, config_dir: str, wg_bin: str = None, wg_quick_bin: str = None, iptables_bin: str = None,
                 gw_iface: str = None, endpoint: str = None):
        super().__init__()
        try:
            self.started = False
            abs_conf_dir = os.path.abspath(config_dir)
            conf_file = os.path.join(abs_conf_dir, CONFIG_FILE_NAME)
            backup_folder = os.path.join(abs_conf_dir, BACKUPS_FOLDER_NAME)
            interfaces_folder = os.path.join(abs_conf_dir, INTERFACES_FOLDER_NAME)
            if not gw_iface:
                gw_iface = run_os_command("ip route | head -1 | xargs | cut -d ' ' -f 5").output
            if not wg_bin:
                wg_bin = run_os_command("whereis wg | tr ' ' '\n' | grep bin").output
            if not wg_quick_bin:
                wg_quick_bin = run_os_command("whereis wg-quick | tr ' ' '\n' | grep bin").output
            if not iptables_bin:
                iptables_bin = run_os_command("whereis iptables | tr ' ' '\n' | grep bin").output
            if endpoint is None:
                try:
                    warning("No endpoint specified. Retrieving public IP address...")
                    endpoint = request.urlopen(IP_RETRIEVER_URL).read().decode("utf-8")
                    debug(f"Public IP is {endpoint}. This will be used as default endpoint.")
                except Exception as e:
                    warning("Unable to obtain server's public IP address. Using private IP instead...")
                    debug(f"Public IP could not be obtained because of: {e}")
                    ip = run_os_command(f"ip a show {gw_iface} | grep inet | head -n1 | xargs | cut -d ' ' -f2") \
                        .output
                    endpoint = ip.split("/")[0]
            info(f"Server endpoint set to {endpoint}.")

            self.config = Config(conf_file, backup_folder, interfaces_folder, wg_bin, wg_quick_bin, iptables_bin,
                                 gw_iface, endpoint)
            self.interfaces = self.config.interfaces
            self.pending_interfaces = OrderedDict()
            self.pending_peers = OrderedDict()
            self.key_manager = KeyManager(wg_bin)
            self.interface_manager = InterfaceManager(self.interfaces, self.key_manager, interfaces_folder,
                                                      iptables_bin,
                                                      wg_quick_bin, gw_iface, fake)
            self.peer_manager = PeerManager(endpoint, self.key_manager, fake)

        except Exception as e:
            fatal(f"Unable to initialize server: {e}")
            exit(1)

    def save_changes(self):
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
        self.load_config()
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
