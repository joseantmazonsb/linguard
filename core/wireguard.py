import logging
import os
from collections import OrderedDict
from logging import info, warning, error, debug
from typing import Dict, Any
from urllib import request
from uuid import uuid4 as gen_uuid

import yaml
from yamlable import YamlAble, yaml_info

from core.exceptions import WireguardError
from core.utils import run_os_command, try_makedir, get_default_gateway, write_lines

# Show no tags when serializing
yaml.emitter.Emitter.process_tag = lambda self, *args, **kw: None


@yaml_info(yaml_tag_ns='')
class BaseConfig(YamlAble):
    optional = False

    def __init__(self):
        self.config = {}

    def save(self, filepath: str):
        """Write configuration to yaml file."""

        debug(f"Saving configuration to {filepath}...")
        with open(filepath, 'w') as file:
            yaml.safe_dump(self, file, sort_keys=False)
        debug(f"Configuration saved!")
        debug("Applying configuration...")
        self.__apply__()
        debug("Configuration applied!")

    def __apply__(self):
        pass

    def load(self, filepath: str):
        debug(f"Restoring configuration from {filepath}...")
        if not os.path.exists(filepath):
            warning(f"Unable to restore configuration file {filepath}: not found.")
        self.__do_load__(filepath)
        debug(f"Configuration restored!")

    def __do_load__(self, filepath: str):
        if os.path.exists(filepath):
            with open(filepath, "r") as backup:
                self.config = list(yaml.safe_load_all(backup))[0]
        self.__set_properties__(filepath)

    def __set_properties__(self, filepath: str):
        pass

    def __to_yaml_dict__(self) -> Dict[str, Any]:
        return self.config.copy()


@yaml_info(yaml_tag_ns='')
class Config(BaseConfig):

    def __set_properties__(self, filepath: str):
        self.config["logger"] = self.config.get("logger", {})
        self.logger_options = LoggerOptions(self.config["logger"])

        self.config["web"] = self.config.get("web", {})
        self.web_options = WebOptions(self.config["web"])

        self.config["linguard"] = self.config.get("linguard", {})
        self.linguard_options = LinguardOptions(self.config["linguard"], os.path.dirname(filepath))

    def __to_yaml_dict__(self):
        copy = super().__to_yaml_dict__()
        copy["linguard"]["interfaces"] = dict(copy["linguard"]["interfaces"])
        return copy

    def __apply__(self):
        super(Config, self).__apply__()
        self.logger_options.apply()
        self.web_options.apply()
        self.linguard_options.apply()


@yaml_info(yaml_tag_ns='')
class VersionInfo(BaseConfig):
    optional = True

    def __set_properties__(self, filepath: str):
        options = self.config.get("version", {})
        self.version = options.get("version", "")
        self.date = options.get("date", "")
        self.commit = options.get("commit", "")

    def save(self, filepath: str):
        raise WireguardError("Unable to update version info.")


class Options:

    def __init__(self, config: Dict):
        self._config = config

    def apply(self):
        debug(f"Applying {self.__class__.__name__}...")
        pass


class LoggerOptions(Options):
    LEVELS = {
        "debug": logging.DEBUG,
        "info": logging.INFO,
        "warning": logging.WARNING,
        "error": logging.ERROR,
        "fatal": logging.FATAL
    }
    DEFAULT_LEVEL = logging.INFO
    LOG_FORMAT = "%(asctime)s [%(levelname)s] %(module)s (%(funcName)s): %(message)s"

    @property
    def overwrite(self):
        return self._config["overwrite"]

    @overwrite.setter
    def overwrite(self, value: bool):
        self._config["overwrite"] = value

    @property
    def level(self):
        return self._config["level"]

    @level.setter
    def level(self, value: str):
        self._config["level"] = value

    @property
    def logfile(self):
        return self._config["logfile"]

    @logfile.setter
    def logfile(self, value: str):
        self._config["logfile"] = value

    def __init__(self, config: Dict):
        super().__init__(config)
        self.logfile = self._config.get("logfile", None)
        self.level = self._config.get("level", logging.getLevelName(self.DEFAULT_LEVEL)).lower()
        if self.level not in self.LEVELS:
            raise WireguardError(f"'{self.level}' is not a valid log level!")
        self.overwrite = self._config.get("overwrite", False)
        if self.logfile:
            self.logfile = os.path.abspath(self.logfile)
        self.apply()

    def apply(self):
        super(LoggerOptions, self).apply()
        if self.overwrite:
            filemode = "w"
        else:
            filemode = "a"
        if self.logfile:
            info(f"Logging to {self.logfile}...")
            handlers = [logging.FileHandler(self.logfile, filemode, "utf-8")]
        else:
            warning("No logfile specified. Logging to stdout...")
            handlers = None
        logging.basicConfig(format=self.LOG_FORMAT, level=self.LEVELS[self.level], handlers=handlers, force=True)


class WebOptions(Options):
    DEFAULT_BINDPORT = 8080
    DEFAULT_LOGIN_ATTEMPTS = 0

    @property
    def bindport(self):
        return self._config["bindport"]

    @bindport.setter
    def bindport(self, value: int):
        self._config["bindport"] = value

    @property
    def login_attempts(self):
        return self._config["login_attempts"]

    @login_attempts.setter
    def login_attempts(self, value: int):
        self._config["login_attempts"] = value

    def __init__(self, config: Dict):
        super().__init__(config)
        self.bindport = self._config.get("bindport", self.DEFAULT_BINDPORT)
        self.login_attempts = self._config.get("login_attempts", self.DEFAULT_LOGIN_ATTEMPTS)


class LinguardOptions(Options):
    IP_RETRIEVER_URL = "https://api.ipify.org"

    @property
    def endpoint(self):
        return self._config["endpoint"]

    @endpoint.setter
    def endpoint(self, value: str):
        self._config["endpoint"] = value

    @property
    def wg_bin(self):
        return self._config["wg_bin"]

    @wg_bin.setter
    def wg_bin(self, value: str):
        self._config["wg_bin"] = value

    @property
    def wg_quick_bin(self):
        return self._config["wg_quick_bin"]

    @wg_quick_bin.setter
    def wg_quick_bin(self, value: str):
        self._config["wg_quick_bin"] = value

    @property
    def iptables_bin(self):
        return self._config["iptables_bin"]

    @iptables_bin.setter
    def iptables_bin(self, value: str):
        self._config["iptables_bin"] = value

    @property
    def interfaces(self):
        return self._config["interfaces"]

    @interfaces.setter
    def interfaces(self, value: Dict):
        self._config["interfaces"] = value

    @property
    def interfaces_folder(self):
        return self._config["interfaces_folder"]

    @interfaces_folder.setter
    def interfaces_folder(self, value: str):
        try_makedir(value)
        self._config["interfaces_folder"] = value

    def __init__(self, config: Dict, config_dir: str):
        super().__init__(config)
        self.endpoint = self._config.get("endpoint", None)
        if not self.endpoint:
            try:
                warning("No endpoint specified. Retrieving public IP address...")
                self.endpoint = request.urlopen(self.IP_RETRIEVER_URL).read().decode("utf-8")
                debug(f"Public IP address is {self.endpoint}. This will be used as default endpoint.")
            except Exception as e:
                error(f"Unable to obtain server's public IP address: {e}")
                ip = run_os_command(
                    f"ip a show {get_default_gateway()} | grep inet | head -n1 | xargs | cut -d ' ' -f2") \
                    .output
                self.endpoint = ip.split("/")[0]
                if not self.endpoint:
                    raise WireguardError("unable to automatically set endpoint.")
                warning(f"Server endpoint set to {self.endpoint}: this might not be a public IP address!")
        self.wg_bin = os.path.abspath(self._config.get("wg_bin", run_os_command("whereis wg | tr ' ' '\n' | grep bin")
                                                       .output))
        self.wg_quick_bin = os.path.abspath(self._config.get("wg_quick_bin",
                                                             run_os_command(
                                                                 "whereis wg-quick | tr ' ' '\n' | grep bin")
                                                             .output))
        self.iptables_bin = os.path.abspath(self._config.get("iptables_bin",
                                                             run_os_command(
                                                                 "whereis iptables | tr ' ' '\n' | grep bin")
                                                             .output))
        self.interfaces_folder = os.path.abspath(self._config.get("interfaces_folder",
                                                                  os.path.join(config_dir,
                                                                               "interfaces")))
        interfaces = self._config.get("interfaces", OrderedDict())
        for iface in interfaces.values():
            iface = Interface.from_dict(iface)
            iface.wg_quick_bin = self.wg_quick_bin
            iface.conf_file = os.path.join(self.interfaces_folder, iface.name) + ".conf"
            interfaces[iface.uuid] = iface
            iface.save()
        self._config["interfaces"] = interfaces

    def apply(self):
        super(LinguardOptions, self).apply()
        for iface in self.interfaces.values():
            iface.wg_quick_bin = self.wg_quick_bin
            was_up = iface.is_up
            iface.down()
            iface.conf_file = os.path.join(self.interfaces_folder, iface.name) + ".conf"
            if was_up:
                iface.up()


@yaml_info(yaml_tag_ns='')
class Interface(YamlAble):
    MIN_PORT_NUMBER = 50000
    MAX_PORT_NUMBER = 65535

    MIN_NAME_LENGTH = 2
    MAX_NAME_LENGTH = 15
    REGEX_NAME = f"^[a-z][a-z\-_0-9]{{{MIN_NAME_LENGTH-1},{MAX_NAME_LENGTH-1}}}$"
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

    def __to_yaml_dict__(self):
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

    @staticmethod
    def from_dict(dct: dict):
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

        if "peers" in dct:
            peers = dct["peers"]
            for peer in peers.values():
                peer = Peer.from_dict(peer)
                peer.interface = iface
                iface.peers[peer.uuid] = peer
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


@yaml_info(yaml_tag_ns='')
class Peer(YamlAble):

    MIN_NAME_LENGTH = 2
    MAX_NAME_LENGTH = 64
    REGEX_NAME = f"^[a-zA-Z][\w\-. ]{{{MIN_NAME_LENGTH-1},{MAX_NAME_LENGTH-1}}}$"

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
        self.confirmed = False

    @property
    def endpoint(self):
        return f"{config.linguard_options.endpoint}:{self.interface.listen_port}"

    def __to_yaml_dict__(self):
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

    @staticmethod
    def from_dict(dct):
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


config = Config()
