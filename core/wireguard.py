from asyncio import sleep
from ctypes import Union
from datetime import datetime
from logging import fatal, info, debug, error
from random import randint
from urllib import request

from core.utils import run_os_command, CommandResult
from web.static.assets.resources import app_name


class Interface:

    def __init__(self, name: str, description: str, gw_iface: str, ipv4_address,
                 listen_port: int, private_key: str, public_key: str, wg_quick_bin: str):
        self.name = name
        self.gw_iface = gw_iface
        self.description = description
        self.ipv4_address = ipv4_address
        self.listen_port = listen_port
        self.wg_quick_bin = wg_quick_bin
        self.private_key = private_key
        self.public_key = public_key
        self.on_up = []
        self.on_down = []

    def up(self) -> bool:
        info(f"Starting interface {self.name}...")
        result = run_os_command(f"{self.wg_quick_bin} up {self.name}")
        if result.successful:
            info(f"Interface {self.name} started.")
        else:
            error(f"Failed to start interface {self.name}: code={result.code} | err={result.err} | out={result.output}")
        return result.successful

    def down(self) -> bool:
        info(f"Stopping interface {self.name}...")
        result = run_os_command(f"{self.wg_quick_bin} down {self.name}")
        if result.successful:
            info(f"Interface {self.name} stopped.")
        else:
            error(f"Failed to stop interface {self.name}: code={result.code} | err={result.err} | out={result.output}")
        return result.successful


class Client:

    def __init__(self, name: str, description: str, ipv4_address: str, private_key: str,
                 public_key: str, nat: bool, endpoint: str, interface: str, dns1: str,
                 dns2: str = None):
        self.name = name
        self.description = description
        self.ipv4_address = ipv4_address
        self.private_key = private_key
        self.public_key = public_key
        self.nat = nat
        self.endpoint = endpoint
        self.interface = interface
        self.dns1 = dns1
        self.dns2 = dns2

    def generate_conf(self) -> str:
        """Generate a wireguard configuration file suitable for this client."""

        iface = f"[Interface]\n" \
                f"PrivateKey = {self.private_key}\n" \
                f"DNS = {self.dns1}"
        if self.dns2:
            iface += f", {self.dns2}"
        iface += "\n"
        iface += f"Address = {self.ipv4_address}\n\n"

        peer = f"[Peer]\n" \
               f"PublicKey = {self.public_key}\n" \
               f"AllowedIPs = {self.ipv4_address}\n" \
               f"Endpoint = {self.endpoint}\n"
        if self.nat:
            peer += "PersistentKeepalive = 25\n"

        return iface + peer


MIN_PORT_NUMBER = 50000
MAX_PORT_NUMBER = 65535
CONFIG_FILE_NAME = "config.yaml"
BACKUPS_FOLDER_NAME = "backups"


class Server:

    def __init__(self, config_dir: str, wg_bin: str, wg_quick_bin: str, iptables_bin: str, gw_iface: str = None):
        if gw_iface:
            self.gw_iface = gw_iface
        else:
            self.gw_iface = run_os_command("ip route | head -1 | xargs | cut -d ' ' -f 5").output
        self.wg_bin = wg_bin
        self.wg_quick_bin = wg_quick_bin
        self.iptables_bin = iptables_bin
        self.interfaces = {}
        self.clients = {}
        self.ports_in_use = []
        conf_dir_stripped = config_dir.strip('/')
        self.conf_file = f"{conf_dir_stripped}/{CONFIG_FILE_NAME}"
        self.backup_folder = f"{conf_dir_stripped}/{BACKUPS_FOLDER_NAME}"
        self.dirty = False
        try:
            debug("Retrieving public IP address...")
            self.ipv4_address = request.urlopen("https://api.ipify.org").read().decode("utf-8")
            debug(f"Public IP is {self.ipv4_address}. This will be used as default endpoint.")
        except Exception as e:
            fatal(f"Unable to obtain server's public IP address: {e}")
            raise e

    # Interfaces

    def add_interface(self, name: str, ipv4_address: str, description: str = ""):
        port = randint(MIN_PORT_NUMBER, MAX_PORT_NUMBER)
        while port in self.ports_in_use:
            port = randint(MIN_PORT_NUMBER, MAX_PORT_NUMBER)
        pubkey = run_os_command(f"{self.wg_bin} pubkey").output
        privkey = run_os_command(f"{self.wg_bin} genkey").output
        iface = Interface(name, description, self.gw_iface, ipv4_address, port, privkey, pubkey, self.wg_quick_bin)
        self.interfaces[name] = iface
        self.ports_in_use.append(port)
        self.__set_iface_rules__(iface)

    def remove_interface(self, iface: Union(Interface, str)):
        if iface in self.interfaces:
            port = self.interfaces[iface].port
            self.ports_in_use.remove(port)
            del self.interfaces[iface]
            return True
        if iface in self.interfaces.values():
            self.ports_in_use.remove(iface.port)
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

    def iface_up(self, iface: Union(Interface, str)) -> bool:
        if iface in self.interfaces:
            return self.interfaces[iface].up().successful
        if iface in self.interfaces.values():
            return iface.up().successful
        return False

    def iface_down(self, iface: Union(Interface, str)) -> bool:
        if iface in self.interfaces:
            return self.interfaces[iface].down().successful
        if iface in self.interfaces.values():
            return iface.down().successful
        return False

    # Clients

    def add_client(self, name: str, interface: str, dns1: str, dns2: str = None, description: str = "",
                   nat: bool = False, ipv4_address: str = None, endpoint: str = None):
        privkey = run_os_command(f"{self.wg_bin} genkey").output
        pubkey = run_os_command(f"{self.wg_bin} pubkey").output
        _endpoint = endpoint
        if not _endpoint:
            _endpoint = self.ipv4_address
        client = Client(name, description, ipv4_address, privkey, pubkey, nat, _endpoint, interface, dns1, dns2)
        self.clients[name] = client

    def remove_client(self, client: Union(Client, str)):
        if client in self.clients:
            del self.clients[client]
            return True
        if client in self.clients.values():
            del self.clients[client.name]
            return True
        return False

    # Changes

    def save_changes(self):
        """Write configuration to yaml file."""
        info("Saving current configuration...")
        self.backup()
        self.dirty = True
        info("Current configuration saved successfully.")

    def backup(self):
        """Back up current configuration by copying the yaml file."""
        info("Backing up current configuration...")
        backup_name = self.conf_file + "-" + datetime.now().strftime("%Y%m%d%H%M%S") + ".bak"
        result = run_os_command(f"cp {self.conf_file} {backup_name}")
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
            restore = run_os_command(f"ls -t {self.backup_folder} | head -1")
        # TODO: restore backup
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
        for iface in self.interfaces:
            self.interfaces[iface].up()
        info("VPN server started.")

    def stop(self):
        info("Stopping VPN server...")
        for iface in self.interfaces:
            self.interfaces[iface].down()
        info("VPN server stopped.")

    def restart(self):
        self.stop()
        sleep(3)
        self.start()


if __name__ == '__main__':
    current_folder = run_os_command("pwd").output.strip('/')
    server_folder = f"{current_folder}/{app_name}"
    wg = Server(server_folder, "wg", "wg-quick", "iptables")
    wg.start()
