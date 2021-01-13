import yaml
from yamlable import yaml_info, YamlAble
import os
from asyncio import sleep
from datetime import datetime
from logging import fatal, info, debug, error, warning
from random import randint
from typing import Union
from urllib import request

from core.utils import run_os_command, generate_privkey, generate_pubkey
from core.wireguard.interface import Interface
from core.wireguard.client import Client

from web.static.assets.resources import app_name

MIN_PORT_NUMBER = 50000
MAX_PORT_NUMBER = 65535
CONFIG_FILE_NAME = "config.yaml"
BACKUPS_FOLDER_NAME = "backups"

# Show no tags when serializing
yaml.emitter.Emitter.process_tag = lambda self, *args, **kw: None


@yaml_info(yaml_tag_ns='')
class Server(YamlAble):

    def __init__(self, config_dir: str, wg_bin: str, wg_quick_bin: str, iptables_bin: str, gw_iface: str = None, endpoint: str = None):
        super().__init__()
        if gw_iface:
            self.gw_iface = gw_iface
        else:
            self.gw_iface = run_os_command("ip route | head -1 | xargs | cut -d ' ' -f 5").output
        self.wg_bin = wg_bin
        self.wg_quick_bin = wg_quick_bin
        self.iptables_bin = iptables_bin
        self.interfaces = {}
        self.clients = {}
        try:
            self.conf_file = f"{os.path.abspath(config_dir)}/{CONFIG_FILE_NAME}"
        except Exception as e:
            fatal(f"Unable to initialize server: {e}")
            exit(1)
        self.backup_folder = f"{os.path.dirname(self.conf_file)}/{BACKUPS_FOLDER_NAME}"
        debug(f"Creating backup folder ({self.backup_folder})...")
        run_os_command(f"mkdir -p {self.backup_folder }")
        self.dirty = False
        self.started = False
        self.endpoint = endpoint
        if self.endpoint is None:
            try:
                debug("Retrieving public IP address...")
                self.endpoint = request.urlopen("https://api.ipify.org").read().decode("utf-8")
                debug(f"Public IP is {self.endpoint}. This will be used as default endpoint.")
            except Exception as e:
                fatal(f"Unable to obtain server's public IP address: {e}")
                raise e

    def __to_yaml_dict__(self):
        """ Called when you call yaml.dump()"""
        return {
            "endpoint": self.endpoint,
            "gw_iface": self.gw_iface,
            "wg_bin": self.wg_bin,
            "wg_quick_bin": self.wg_quick_bin,
            "iptables_bin": self.iptables_bin,
            "interfaces": self.interfaces,
            "clients": self.clients,
        }

    def __from_dict__(self, config: dict):
        self.endpoint = config["endpoint"]
        self.gw_iface = config["gw_iface"]
        self.wg_bin = config["wg_bin"]
        self.wg_quick_bin = config["wg_quick_bin"]
        self.iptables_bin = config["iptables_bin"]
        self.interfaces = self.clients = {}
        interfaces = config["interfaces"]
        for iface in interfaces.values():
            iface = Interface.from_dict(iface)
            iface.wg_quick_bin = self.wg_quick_bin
            iface.gw_iface = self.gw_iface
            self.interfaces[iface.name] = iface
        clients = config["clients"]
        for client in clients.values():
            client = Client.from_dict(client)
            client.endpoint = self.endpoint
            self.clients[client.name] = client

    # Interfaces

    def is_port_in_use(self, port: int) -> bool:
        for iface in self.interfaces.values():
            if port == iface.listen_port:
                return True
        return False

    def add_interface(self, name: str, ipv4_address: str, description: str = ""):
        port = randint(MIN_PORT_NUMBER, MAX_PORT_NUMBER)
        while self.is_port_in_use(port):
            port = randint(MIN_PORT_NUMBER, MAX_PORT_NUMBER)
        privkey = generate_privkey(self.wg_bin)
        pubkey = generate_pubkey(self.wg_bin, privkey)
        iface = Interface(name, description, self.gw_iface, ipv4_address, port, privkey, pubkey, self.wg_quick_bin)
        self.interfaces[name] = iface
        self.__set_iface_rules__(iface)

    def remove_interface(self, iface: Union[Interface, str]):
        if iface in self.interfaces:
            del self.interfaces[iface]
            return True
        if iface in self.interfaces.values():
            del self.interfaces[iface.name]
            return True
        return False

    def __set_iface_rules__(self, iface: Interface):
        iface.on_up.append(f"{self.iptables_bin} -I FORWARD -i {iface.name} -j ACCEPT")
        iface.on_up.append(f"{self.iptables_bin} -I FORWARD -o {iface.name} -j ACCEPT")
        iface.on_up.append(f"{self.iptables_bin} -t nat -I POSTROUTING -o {iface.gw_iface} -j MASQUERADE")

        iface.on_down.append(f"{self.iptables_bin} -D FORWARD -i {iface.name} -j ACCEPT")
        iface.on_down.append(f"{self.iptables_bin} -D FORWARD -o {iface.name} -j ACCEPT")
        iface.on_down.append(f"{self.iptables_bin} -D nat -I POSTROUTING -o {iface.gw_iface} -j MASQUERADE")

    def iface_up(self, iface: Union[Interface, str]) -> bool:
        if iface in self.interfaces:
            return self.interfaces[iface].up().successful
        if iface in self.interfaces.values():
            return iface.up().successful
        return False

    def iface_down(self, iface: Union[Interface, str]) -> bool:
        if iface in self.interfaces:
            return self.interfaces[iface].down().successful
        if iface in self.interfaces.values():
            return iface.down().successful
        return False

    # Clients

    def add_client(self, name: str, interface: str, dns1: str, dns2: str = None, description: str = "",
                   nat: bool = False, ipv4_address: str = None, endpoint: str = None):
        if interface not in self.interfaces:
            warning(f"Interface '{interface}' not registered.")
            return
        privkey = generate_privkey(self.wg_bin)
        pubkey = generate_pubkey(self.wg_bin, privkey)
        _endpoint = endpoint
        if not _endpoint:
            _endpoint = self.endpoint
        ip = ipv4_address
        if not ip:
            ip = "10.0.100.2/24"
        client = Client(name, description, ip, privkey, pubkey, nat, _endpoint, interface, dns1, dns2)
        self.clients[name] = client
        self.interfaces[interface].peers.append(client)

    def remove_client(self, client: Union[Client, str]):
        if client in self.clients:
            c = self.clients[client]
            self.interfaces[c.interface].peers.remove()
            del self.clients[client]
            return True
        if client in self.clients.values():
            self.interfaces[client.interface].peers.remove()
            del self.clients[client.name]
            return True
        return False

    # Changes

    def save_changes(self):
        """Write configuration to yaml file."""
        info("Saving current configuration...")
        self.backup()
        with open(self.conf_file, 'w') as file:
            yaml.safe_dump(self, file, sort_keys=False)
        self.dirty = True
        info("Current configuration saved successfully.")

    def backup(self):
        """Back up current configuration by copying the yaml file."""
        info("Backing up current configuration...")
        if not os.path.isfile(self.conf_file):
            warning("Unable to create backup. No configuration file exist.")
            return
        backup_file = f"{self.backup_folder}/{CONFIG_FILE_NAME}.bak{datetime.now().strftime('%Y%m%d%H%M%S')}"
        result = run_os_command(f"cp {self.conf_file} {backup_file}")
        if not result.successful:
            error(f"Failed to create backup: code={result.code} | err={result.err} | out={result.output}")
            return
        info("Backup completed.")

    def restore_backup(self, path: str = None):
        """Restore configuration from a previously backed up yaml file."""
        info("Restoring backup...")
        restore = path
        if not restore:
            # Restore most recent backup
            restore = os.path.join(self.backup_folder, run_os_command(f"ls -t {self.backup_folder} | head -1").output)
            debug(f"No backup specified, restoring latest ({restore})...")
        with open(restore, "r") as backup:
            config = list(yaml.safe_load_all(backup))[0]
            self.__from_dict__(config)
        self.dirty = True
        info("Backup restored.")

    def discard_changes(self):
        """Discard all **unsaved** changes by restoring the configuration saved in the yaml file."""
        if self.dirty:
            self.restore_backup()
            self.dirty = False

    def apply_changes(self):
        """Write current configuration to wireguard files and restart all interfaces."""
        self.stop()
        self.save_changes()
        # TODO: write to wireguard .conf files
        self.dirty = False
        self.start()

    def start(self):
        info("Starting VPN server...")
        if self.started:
            warning("Unable to start VPN server: already started.")
            return
        for iface in self.interfaces.values():
            iface.up()
        self.started = True
        info("VPN server started.")

    def stop(self):
        info("Stopping VPN server...")
        if not self.started:
            warning("Unable to stop VPN server: already stopped.")
            return
        for iface in self.interfaces.values():
            iface.down()
        self.started = False
        info("VPN server stopped.")

    def restart(self):
        self.stop()
        sleep(3)
        self.start()


if __name__ == '__main__':
    import logging
    logging.basicConfig(level=logging.DEBUG)
    server_folder = app_name.lower()
    wg = Server(server_folder, "wg", "wg-quick", "iptables")
    wg.add_interface("scranton-vpn", "10.0.100.1/24", "VPN for Scranton branch")
    wg.add_interface("ny-vpn", "10.0.101.1/24", "VPN for NY branch")
    wg.add_client("jim", "scranton-vpn", "8.8.8.8")
    wg.add_client("karen", "scranton-vpn", "8.8.8.8")
    wg.save_changes()
