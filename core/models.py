import http
import os
import re
from collections import OrderedDict
from logging import info, warning, error, debug
from random import randint
from time import sleep
from typing import Dict, Any, Type, List, Mapping, TypeVar
from uuid import uuid4 as gen_uuid

from coolname import generate_slug
from yamlable import YamlAble, yaml_info, Y

from core.exceptions import WireguardError
from system_utils import run_os_command, write_lines, try_makedir, get_wg_interface_status

K = TypeVar('K')
V = TypeVar('V')


class EnhancedDict(Dict, Mapping[K, V]):

    def set_contents(self, dct: "EnhancedDict"):
        """
        Clear the dictionary and fill it with the values of the given one.

        :param dct:
        :return:
        """
        self.clear()
        self.update(dct)

    def sort(self, order_by):
        self.set_contents(OrderedDict(sorted(self.items(), key=order_by)))

    def get_key_by_attr(self, attr: str, attr_value: str) -> K:
        """
        Get the first key (or None) of the dictionary which contains an attribute whose value is equal to attr_value.

        :param attr: Attribute to compare.
        :param attr_value: Value to compare.
        :return: The first matching key or None.
        """
        return next(iter(filter(lambda k: k.__getattribute__(attr) == attr_value, self.keys())), None)

    def get_value_by_attr(self, attr: str, attr_value: str) -> V:
        """
        Get the first value (or None) of the dictionary which contains an attribute whose value is equal to attr_value.

        :param attr: Attribute to compare.
        :param attr_value: Value to compare.
        :return: The first matching value or None.
        """
        return next(iter(filter(lambda v: v.__getattribute__(attr) == attr_value, self.values())), None)


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

    @property
    def wg_quick_bin(self):
        from core.config.linguard_config import config
        return config.wg_quick_bin

    def __init__(self, name: str, description: str, gw_iface: str, ipv4_address: str, listen_port: int, auto: bool,
                 on_up: List[str], on_down: List[str], uuid: str = "", private_key: str = "",
                 public_key: str = "", peers: Dict[str, "Peer"] = None):
        self.name = name
        self.gw_iface = gw_iface
        self.description = description
        self.ipv4_address = ipv4_address
        self.listen_port = listen_port
        self.auto = auto
        self.on_up = on_up
        self.on_down = on_down
        self.uuid = uuid or gen_uuid().hex
        self.peers = peers or OrderedDict()
        for peer in self.peers.values():
            peer.interface = self
        from core.utils import generate_privkey, generate_pubkey
        from core.config.linguard_config import config
        self.conf_file = f"{os.path.join(config.interfaces_folder, self.name)}.conf"
        self.private_key = private_key or generate_privkey()
        if not private_key:
            warning("Generating new public key because no private key was provided.")
            self.public_key = generate_pubkey(self.private_key)
        else:
            self.public_key = public_key or generate_pubkey(self.private_key)

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
    def __from_yaml_dict__(cls,  # type: Type[Y]
                           dct,  # type: Dict[str, Any]
                           yaml_tag  # type: str
                           ):  # type: (...) -> Y
        """ This optional method is called when you call yaml.load()"""
        uuid = dct["uuid"]
        name = dct["name"]
        description = dct["description"]
        gw_iface = dct["gw_iface"]
        ipv4_address = dct["ipv4_address"]
        listen_port = dct["listen_port"]
        private_key = dct["private_key"]
        public_key = dct["public_key"]
        auto = dct["auto"]
        on_up = dct.get("on_up", [])
        on_down = dct.get("on_down", [])
        peers = dct.get("peers", None)
        iface = Interface(name=name, description=description, gw_iface=gw_iface, ipv4_address=ipv4_address,
                          listen_port=listen_port, auto=auto, uuid=uuid, private_key=private_key,
                          public_key=public_key, on_up=on_up, on_down=on_down, peers=peers)
        return iface

    def generate_conf(self) -> str:
        """Generate the wireguard configuration for this interface."""
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
        return iface + peers

    def save(self):
        """Store the current wireguard configuration for this interface in the file system."""
        debug(f"Saving configuration of interface {self.name} to {self.conf_file}...")
        try_makedir(os.path.dirname(self.conf_file))
        write_lines(self.generate_conf(), self.conf_file)
        debug(f"Configuration saved!")

    @property
    def is_up(self):
        return run_os_command(f"ip a | grep -w {self.name}").successful

    @property
    def is_down(self):
        return not self.is_up

    @property
    def status(self):
        from core.config.linguard_config import config
        return get_wg_interface_status(config.wg_bin, self.name)

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

    def apply(self):
        self.down()
        self.save()
        self.up()

    def restart(self):
        self.down()
        sleep(1)
        self.up()

    def remove(self):
        self.down()
        if os.path.exists(self.conf_file):
            os.remove(self.conf_file)
        del interfaces[self.uuid]
        interfaces.sort()
        for peer in self.peers:
            from core.modules import peer_manager
            peer_manager.remove_peer(peer)

    def edit(self, name: str, description: str, ipv4_address: str,
                       port: int, gw_iface: str, auto: bool, on_up: List[str], on_down: List[str]):
        self.name = name
        self.gw_iface = gw_iface
        self.description = description
        self.ipv4_address = ipv4_address
        self.listen_port = port
        self.auto = auto
        self.on_up = on_up
        self.on_down = on_down
        from core.config.linguard_config import config
        self.conf_file = f"{os.path.join(config.interfaces_folder, self.name)}.conf"

    @classmethod
    def generate_valid_name(cls) -> str:
        name = generate_slug(2)[:cls.MAX_NAME_LENGTH]
        for iface in interfaces.values():
            if iface.name == name:
                return cls.generate_valid_name()
        return name

    @classmethod
    def is_name_valid(cls, name: str) -> bool:
        return re.match(cls.REGEX_NAME, name) is not None

    @classmethod
    def is_name_in_use(cls, name: str, interface: "Interface") -> bool:
        iface = interfaces.get_value_by_attr("name", name)
        if iface:
            if iface == interface:
                return False
            return True

    @classmethod
    def is_ip_in_use(cls, ip: str, interface_to_exclude: "Interface" = None) -> bool:
        for iface in filter(lambda i: i != interface_to_exclude, interfaces.values()):
            if iface.ipv4_address == ip:
                return True
        return False

    @classmethod
    def is_port_in_use(cls, port: int, interface_to_exclude: "Interface" = None) -> bool:
        for iface in filter(lambda i: i != interface_to_exclude, interfaces.values()):
            if iface.listen_port == port:
                return True
        return False

    @classmethod
    def get_unused_port(cls) -> int:
        tries = 100
        for i in range(0, tries):
            port = randint(Interface.MIN_PORT_NUMBER, Interface.MAX_PORT_NUMBER)
            if not Interface.is_port_in_use(port):
                return port
        raise WireguardError(f"Unable to obtain a free port (tried {tries} times)", http.HTTPStatus.BAD_REQUEST)


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
class InterfaceDict(EnhancedDict, YamlAble, Mapping[K, V]):
    @classmethod
    def __from_yaml_dict__(cls,  # type: Type[Y]
                           dct,  # type: Dict[str, Any]
                           yaml_tag  # type: str
                           ):  # type: (...) -> Y
        i = InterfaceDict()
        i.update(dct)
        return i

    def __to_yaml_dict__(self):  # type: (...) -> Dict[str, Any]
        return self

    def sort(self, order_by=lambda pair: pair[1].name):
        super(InterfaceDict, self).sort(order_by)


interfaces: InterfaceDict[str, Interface]
interfaces = InterfaceDict()
