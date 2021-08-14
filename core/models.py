from collections import OrderedDict
from logging import info, warning, error, debug
from typing import Dict, Any, Type
from uuid import uuid4 as gen_uuid

from yamlable import YamlAble, yaml_info, Y

from core.exceptions import WireguardError
from core.utils import run_os_command, write_lines


@yaml_info(yaml_tag='interface')
class Interface(YamlAble):
    MIN_PORT_NUMBER = 50000
    MAX_PORT_NUMBER = 65535

    MIN_NAME_LENGTH = 2
    MAX_NAME_LENGTH = 15
    REGEX_NAME = f"^[a-z][a-z\-_0-9]{{{MIN_NAME_LENGTH - 1},{MAX_NAME_LENGTH - 1}}}$"
    REGEX_IPV4_PARTIAL = "([1-9]|[1-9]\d|1\d{2}|2[0-4]\d|25[0-5])(\.(\d|[1-9]\d|1\d{2}|2[0-4]\d|25[0-5])){3}"
    REGEX_IPV4 = f"^{REGEX_IPV4_PARTIAL}$"
    REGEX_IPV4_CIDR = f"^{REGEX_IPV4_PARTIAL}\/(3[0-2]|[1-2]\d|\d)$"

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
        self.peers = OrderedDict()

    def __to_yaml_dict__(self):  # type: (...) -> Dict[str, Any]
        """ Called when you call yaml.dump()"""
        return {
            "uuid": self.uuid,
            "name": self.name,
            "description": self.description,
            "gw_iface": self.gw_iface,
            "ipv4_address": self.ipv4_address,
            "listen_port": self.listen_port,
            "private_key": self.private_key,
            "public_key": self.public_key,
            "auto": self.auto,
            "on_up": self.on_up,
            "on_down": self.on_down,
            "peers": dict(self.peers)
        }

    @classmethod
    def __from_yaml_dict__(cls,      # type: Type[Y]
                           dct,      # type: Dict[str, Any]
                           yaml_tag  # type: str
                           ):  # type: (...) -> Y
        """ This optional method is called when you call yaml.load()"""
        if "uuid" in dct:
            uuid = dct["uuid"]
        else:
            uuid = gen_uuid().hex
        name = dct["name"]
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
        iface = Interface(uuid, name, None, description, gw_iface,
                          ipv4_address, listen_port, private_key,
                          public_key, wg_quick_bin, auto)
        iface.on_up = dct["on_up"]
        iface.on_down = dct["on_down"]
        iface.peers = dct["peers"]
        for peer in iface.peers.values():
            peer.interface = iface
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
        for peer in self.peers.values():
            peers += f"\n[Peer]\n" \
                     f"PublicKey = {peer.public_key}\n" \
                     f"AllowedIPs = {peer.ipv4_address}\n"
        conf = iface + peers
        debug(f"Saving configuration of interface {self.name} to {self.conf_file}...")
        write_lines(conf, self.conf_file)
        debug(f"Configuration saved!")
        return conf

    @property
    def is_up(self):
        return run_os_command(f"ip a | grep -w {self.name}").successful

    @property
    def is_down(self):
        return not self.is_up

    def up(self):
        info(f"Starting interface {self.name}...")
        if self.is_up:
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
        if self.is_down:
            warning(f"Unable to bring {self.name} down: already down.")
            return
        result = run_os_command(f"sudo {self.wg_quick_bin} down {self.conf_file}")
        if result.successful:
            info(f"Interface {self.name} stopped.")
        else:
            error(f"Failed to stop interface {self.name}: code={result.code} | err={result.err} | out={result.output}")
            raise WireguardError(result.err)


@yaml_info(yaml_tag='peer')
class Peer(YamlAble):
    MIN_NAME_LENGTH = 2
    MAX_NAME_LENGTH = 64
    REGEX_NAME = f"^[a-zA-Z][\w\-. ]{{{MIN_NAME_LENGTH - 1},{MAX_NAME_LENGTH - 1}}}$"

    def __init__(self, uuid: str, name: str, description: str, ipv4_address: str, private_key: str, public_key: str,
                 nat: bool, interface: Interface, dns1: str, dns2: str = None):
        self.uuid = uuid
        self.name = name
        self.description = description
        self.ipv4_address = ipv4_address
        self.private_key = private_key
        self.public_key = public_key
        self.nat = nat
        self.interface = interface
        self.dns1 = dns1
        self.dns2 = dns2

    @property
    def endpoint(self):
        from core.config.linguard_config import config
        return f"{config.endpoint}:{self.interface.listen_port}"

    def __to_yaml_dict__(self):  # type: (...) -> Dict[str, Any]
        """ Called when you call yaml.dump()"""
        return {
            "uuid": self.uuid,
            "name": self.name,
            "description": self.description,
            "ipv4_address": self.ipv4_address,
            "private_key": self.private_key,
            "public_key": self.public_key,
            "nat": self.nat,
            "dns1": self.dns1,
            "dns2": self.dns2
        }

    @classmethod
    def __from_yaml_dict__(cls,  # type: Type[Y]
                           dct,  # type: Dict[str, Any]
                           yaml_tag  # type: str
                           ):  # type: (...) -> Y
        """ This optional method is called when you call yaml.load()"""
        return Peer(dct["uuid"], dct["name"], dct["description"], dct["ipv4_address"], dct["private_key"],
                    dct["public_key"], dct["nat"], None, dct["dns1"], dct["dns2"])

    def generate_conf(self) -> str:
        """Generate a wireguard configuration file suitable for this client."""

        iface = f"[Interface]\n" \
                f"PrivateKey = {self.private_key}\n"
        iface += f"Address = {self.ipv4_address}\n" \
                 f"DNS = {self.dns1}"
        if self.dns2:
            iface += f", {self.dns2}\n"
        else:
            iface += "\n"
        peer = f"\n[Peer]\n" \
               f"PublicKey = {self.public_key}\n" \
               f"AllowedIPs = 0.0.0.0/0\n" \
               f"Endpoint = {self.endpoint}\n"
        if self.nat:
            peer += "PersistentKeepalive = 25\n"

        return iface + peer


@yaml_info(yaml_tag='interfaces')
class InterfaceDict(Dict[str, Interface], YamlAble):

    def get_by_name(self, name: str):
        for k, v in self.items():
            if v.name == name:
                return v
        return None

    def set_contents(self, dct: "InterfaceDict"):
        """
        Clear the dictionary and fill it with the values of the given one.

        :param dct:
        :return:
        """
        self.clear()
        self.update(dct)

    @classmethod
    def __from_yaml_dict__(cls,      # type: Type[Y]
                           dct,      # type: Dict[str, Any]
                           yaml_tag  # type: str
                           ):  # type: (...) -> Y
        i = InterfaceDict()
        i.update(dct)
        return i

    def __to_yaml_dict__(self):  # type: (...) -> Dict[str, Any]
        return self


interfaces = InterfaceDict()
