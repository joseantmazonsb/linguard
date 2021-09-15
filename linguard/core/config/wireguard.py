import os
from logging import debug, warning, error
from typing import Dict, Type, Any
from urllib import request

from yamlable import yaml_info, Y

from linguard.common.utils.network import get_default_gateway
from linguard.common.utils.system import Command
from linguard.core.config.base import BaseConfig
from linguard.core.exceptions import WireguardError


@yaml_info(yaml_tag='wireguard')
class WireguardConfig(BaseConfig):
    __IP_RETRIEVER_URL = "https://api.ipify.org"

    endpoint: str
    wg_bin: str
    wg_quick_bin: str
    iptables_bin: str
    __interfaces_folder: str

    @property
    def interfaces_folder(self):
        return self.__interfaces_folder

    @interfaces_folder.setter
    def interfaces_folder(self, value: str):
        self.__interfaces_folder = value

    def __init__(self):
        self.load_defaults()

    def load_defaults(self):
        self.endpoint = ""
        self.wg_bin = Command("whereis wg | tr ' ' '\n' | grep bin").run().output
        self.wg_quick_bin = Command("whereis wg-quick | tr ' ' '\n' | grep bin").run().output
        self.iptables_bin = Command("whereis iptables | tr ' ' '\n' | grep bin").run().output
        self.__interfaces_folder = os.path.join(os.path.abspath(os.getcwd()), "interfaces")
        from linguard.core.models import interfaces
        self.interfaces = interfaces

    def load(self, config: "WireguardConfig"):
        self.endpoint = config.endpoint or self.endpoint
        if not self.endpoint:
            warning("No endpoint specified. Retrieving public IP address...")
            self.__set_endpoint__()
        self.wg_bin = config.wg_bin or self.wg_bin
        self.wg_quick_bin = config.wg_quick_bin or self.wg_quick_bin
        self.iptables_bin = config.iptables_bin or self.iptables_bin
        self.interfaces_folder = config.interfaces_folder or self.interfaces_folder
        if config.interfaces:
            self.interfaces.set_contents(config.interfaces)
        for iface in self.interfaces.values():
            iface.conf_file = os.path.join(self.interfaces_folder, iface.name) + ".conf"
            iface.save()

    def __set_endpoint__(self):
        try:
            self.endpoint = request.urlopen(self.__IP_RETRIEVER_URL).read().decode("utf-8")
            debug(f"Public IP address is {self.endpoint}. This will be used as default endpoint.")
        except Exception as e:
            error(f"Unable to obtain server's public IP address: {e}")
            ip = (Command(f"ip a show {get_default_gateway()} | grep inet | head -n1 | xargs | cut -d ' ' -f2")
                  .run().output)
            self.endpoint = ip.split("/")[0]
            if not self.endpoint:
                raise WireguardError("unable to automatically set endpoint.")
            warning(f"Server endpoint set to {self.endpoint}: this might not be a public IP address!")

    @classmethod
    def __from_yaml_dict__(cls,  # type: Type[Y]
                           dct,  # type: Dict[str, Any]
                           yaml_tag=""
                           ):  # type: (...) -> Y
        config = WireguardConfig()
        config.endpoint = dct.get("endpoint", None) or config.endpoint
        config.wg_bin = dct.get("wg_bin", None) or config.wg_bin
        config.wg_quick_bin = dct.get("wg_quick_bin", None) or config.wg_quick_bin
        config.iptables_bin = dct.get("iptables_bin", None) or config.iptables_bin
        config.interfaces_folder = dct.get("interfaces_folder", None) or config.interfaces_folder
        config.interfaces = dct.get("interfaces", None) or config.interfaces
        for iface in config.interfaces.values():
            iface.conf_file = os.path.join(config.interfaces_folder, iface.name) + ".conf"
            iface.save()
        return config

    def __to_yaml_dict__(self):  # type: (...) -> Dict[str, Any]
        return {
            "endpoint": self.endpoint,
            "wg_bin": self.wg_bin,
            "wg_quick_bin": self.wg_quick_bin,
            "iptables_bin": self.iptables_bin,
            "interfaces_folder": self.interfaces_folder,
            "interfaces": self.interfaces,
        }

    def apply(self):
        super(WireguardConfig, self).apply()
        for iface in self.interfaces.values():
            was_up = iface.is_up
            iface.down()
            if os.path.exists(iface.conf_file):
                os.remove(iface.conf_file)
            iface.conf_file = os.path.join(self.interfaces_folder, iface.name) + ".conf"
            if was_up:
                iface.up()


config = WireguardConfig()
