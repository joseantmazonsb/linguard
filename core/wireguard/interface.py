from audioop import error
from logging import info

from yamlable import YamlAble, yaml_info

from core.utils import run_os_command


@yaml_info(yaml_tag_ns='')
class Interface(YamlAble):

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
        self.peers = []

    def __to_yaml_dict__(self):
        """ Called when you call yaml.dump()"""
        return {
            "name": self.name,
            "description": self.description,
            "ipv4_address": self.ipv4_address,
            "listen_port": self.listen_port,
            "private_key": self.private_key,
            "public_key": self.public_key,
            "on_up": self.on_up,
            "on_down": self.on_down
        }

    @staticmethod
    def from_dict(dct):
        """ This optional method is called when you call yaml.load()"""
        iface = Interface(dct["name"], dct["description"], "", dct["ipv4_address"], dct["listen_port"],
                          dct["private_key"], dct["public_key"], "")
        iface.on_up = dct["on_up"]
        iface.on_down = dct["on_down"]
        return iface

    def generate_conf(self) -> str:
        """Generate a wireguard configuration file suitable for this client."""

        iface = f"[Interface]\n" \
                f"PrivateKey = {self.private_key}\n" \
                f"Address = {self.ipv4_address}\n" \
                f"ListenPort = {self.listen_port}\n"
        for cmd in self.on_up:
            iface += f"PostUp = {cmd}\n"
        for cmd in self.on_down:
            iface += f"PostDown = {cmd}\n"

        peers = ""
        for peer in self.peers:
            peers += f"\n[Peer]\n" \
                     f"PublicKey = {peer.public_key}\n" \
                     f"AllowedIPs = {peer.ipv4_address}\n"
        return iface + peers

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
