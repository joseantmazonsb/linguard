from logging import info, warning, debug, error
from uuid import uuid4 as gen_uuid

from yamlable import YamlAble, yaml_info

from core.utils import run_os_command, write_lines
from core.wireguard.exceptions import WireguardError


@yaml_info(yaml_tag_ns='')
class Interface(YamlAble):

    MIN_PORT_NUMBER = 50000
    MAX_PORT_NUMBER = 65535

    REGEX_NAME = "^[a-zA-Z0-9_\-]+$"
    REGEX_IPV4 = "^([1-9]|[1-9]\d|1\d{2}|2[0-4]\d|25[0-5])(\.(\d|[1-9]\d|1\d{2}|2[0-4]\d|25[0-5])){3}\/(3[0-2]|[1-2]\d|\d)$"

    def __init__(self, uuid: str, name: str, conf_file: str, description: str, gw_iface: str, ipv4_address,
                 listen_port: int, private_key: str, public_key: str, wg_quick_bin: str, auto: bool):
        self.uuid = uuid
        self.name = name
        self.conf_file = conf_file
        self.gw_iface = gw_iface
        self.description = description
        self.ipv4_address = ipv4_address
        self.listen_port = listen_port
        self.wg_quick_bin = wg_quick_bin
        self.private_key = private_key
        self.public_key = public_key
        self.auto = auto
        self.on_up = []
        self.on_down = []
        self.peers = []

    def __to_yaml_dict__(self):
        """ Called when you call yaml.dump()"""
        return {
            "uuid": self.uuid,
            "name": self.name,
            "conf_file": self.conf_file,
            "description": self.description,
            "gw_iface": self.gw_iface,
            "ipv4_address": self.ipv4_address,
            "listen_port": self.listen_port,
            "private_key": self.private_key,
            "public_key": self.public_key,
            "auto": self.auto,
            "on_up": self.on_up,
            "on_down": self.on_down
        }

    @staticmethod
    def from_dict(dct):
        """ This optional method is called when you call yaml.load()"""
        if "uuid" in dct:
            uuid = dct["uuid"]
        else:
            uuid = gen_uuid().hex
        name = dct["name"]
        conf_file = dct["conf_file"]
        description = dct["description"]
        gw_iface = dct["gw_iface"]
        ipv4_address = dct["ipv4_address"]
        listen_port = dct["listen_port"]
        private_key = dct["private_key"]
        public_key = dct["public_key"]
        auto = dct["auto"]
        wg_quick_bin = None
        if "wg_quick_bin" in dct:
            wg_quick_bin = dct["wg_quick_bin"]
        iface = Interface(uuid, name, conf_file, description, gw_iface,
                          ipv4_address, listen_port, private_key,
                          public_key, wg_quick_bin, auto)
        iface.on_up = dct["on_up"]
        iface.on_down = dct["on_down"]
        return iface

    def save(self) -> str:
        """Generate a wireguard configuration file suitable for this interface and store it."""

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
        conf = iface + peers
        debug(f"Saving configuration of interface {self.name} to {self.conf_file}...")
        write_lines(conf, self.conf_file)
        debug(f"Configuration saved!")
        return conf

    def up(self):
        info(f"Starting interface {self.name}...")
        is_up = run_os_command(f"ip a | grep -w {self.name}").successful
        if is_up:
            warning(f"Unable to bring {self.name} up: already up.")
            return
        self.save()
        result = run_os_command(f"sudo {self.wg_quick_bin} up {self.conf_file}")
        if result.successful:
            info(f"Interface {self.name} started.")
        else:
            error(f"Failed to start interface {self.name}: code={result.code} | err={result.err} | out={result.output}")
            raise WireguardError(result.err)

    def down(self):
        info(f"Stopping interface {self.name}...")
        is_down = not run_os_command(f"ip a | grep -w {self.name}").successful
        if is_down:
            warning(f"Unable to bring {self.name} down: already down.")
            return
        result = run_os_command(f"sudo {self.wg_quick_bin} down {self.conf_file}")
        if result.successful:
            info(f"Interface {self.name} stopped.")
        else:
            error(f"Failed to stop interface {self.name}: code={result.code} | err={result.err} | out={result.output}")
            raise WireguardError(result.err)
