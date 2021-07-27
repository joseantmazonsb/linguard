import logging
import os
from collections import OrderedDict
from http.client import BAD_REQUEST
from logging import info, warning, error, debug
from typing import Dict, Any

import yaml
from urllib import request
from yamlable import YamlAble, yaml_info

from core.exceptions import WireguardError
from core.utils import run_os_command, try_makedir
from core.wireguard import Interface

# Show no tags when serializing
yaml.emitter.Emitter.process_tag = lambda self, *args, **kw: None


@yaml_info(yaml_tag_ns='')
class BaseConfig(YamlAble):
    optional = False

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.config = {}

    def save(self):
        """Write configuration to yaml file."""

        debug(f"Saving configuration ({self.__class__.__name__})...")
        with open(self.filepath, 'w') as file:
            yaml.safe_dump(self, file, sort_keys=False)
        debug(f"Configuration ({self.__class__.__name__}) saved!")

    def load(self):
        debug(f"Restoring configuration ({self.__class__.__name__})...")
        if not self.filepath:
            msg = "Unable to restore configuration file: no path specified."
            error(msg)
            raise WireguardError(msg, BAD_REQUEST)
        if not os.path.exists(self.filepath):
            warning(f"Unable to restore configuration file {self.filepath}: not found.")
        self.__do_load__()
        debug(f"Configuration ({self.__class__.__name__}) restored from {self.filepath}.")

    def __do_load__(self):
        if os.path.exists(self.filepath):
            with open(self.filepath, "r") as backup:
                self.config = list(yaml.safe_load_all(backup))[0]
        self.__set_properties__()

    def __set_properties__(self):
        pass

    def __to_yaml_dict__(self) -> Dict[str, Any]:
        return self.config.copy()


@yaml_info(yaml_tag_ns='')
class Config(BaseConfig):

    DEFAULT_BINDPORT = 8080
    DEFAULT_LOGIN_ATTEMPTS = 0

    LEVELS = {
        "debug": logging.DEBUG,
        "info": logging.INFO,
        "warning": logging.WARNING,
        "error": logging.ERROR,
        "fatal": logging.FATAL
    }
    DEFAULT_LEVEL = logging.INFO
    LOG_FORMAT = "%(asctime)s [%(levelname)s] %(module)s (%(funcName)s): %(message)s"

    IP_RETRIEVER_URL = "https://api.ipify.org"

    def web(self) -> Dict:
        return self.config["web"]

    def logger(self) -> Dict:
        return self.config["logger"]

    def linguard(self) -> Dict:
        return self.config["linguard"]

    def __set_properties__(self):
        self.__set_logger_properties()
        self.__set_web_properties()
        self.__set_linguard_properties()

    def __set_logger_properties(self):
        self.config["logger"] = self.config.get("logger", {})
        options = self.config["logger"]

        options["logfile"] = options.get("logfile", None)
        options["level"] = options.get("level", logging.getLevelName(self.DEFAULT_LEVEL)).lower()
        level = options["level"]
        if level not in self.LEVELS:
            raise WireguardError(f"'{level}' is not a valid log level!")
        options["overwrite"] = options.get("overwrite", False)
        if options["overwrite"]:
            filemode = "w"
        else:
            filemode = "a"
        logfile = options["logfile"]
        if logfile:
            logfile = os.path.abspath(logfile)
            options["logfile"] = logfile
            info(f"Logging to {logfile}...")
            handlers = [logging.FileHandler(logfile, filemode, "utf-8")]
        else:
            warning("No logfile specified. Logging to stdout...")
            handlers = None
        logging.basicConfig(format=self.LOG_FORMAT, level=self.LEVELS[level], handlers=handlers, force=True)

    def __set_web_properties(self):
        self.config["web"] = self.config.get("web", {})
        options = self.config["web"]
        options["bindport"] = options.get("bindport", self.DEFAULT_BINDPORT)
        options["login_attempts"] = options.get("login_attempts", self.DEFAULT_LOGIN_ATTEMPTS)

    def __set_linguard_properties(self):
        self.config["linguard"] = self.config.get("linguard", {})
        options = self.config["linguard"]
        options["gw_iface"] = options.get("gw_iface", run_os_command("ip route | head -1 | xargs | cut -d ' ' -f 5").
                                          output)
        options["endpoint"] = options.get("endpoint", None)
        if not options["endpoint"]:
            try:
                warning("No endpoint specified. Retrieving public IP address...")
                options["endpoint"] = request.urlopen(self.IP_RETRIEVER_URL).read().decode("utf-8")
                debug(f"Public IP address is {options['endpoint']}. This will be used as default endpoint.")
            except Exception as e:
                error(f"Unable to obtain server's public IP address: {e}")
                ip = run_os_command(f"ip a show {options['gw_iface']} | grep inet | head -n1 | xargs | cut -d ' ' -f2") \
                    .output
                options["endpoint"] = ip.split("/")[0]
                if not options["endpoint"]:
                    raise WireguardError("unable to automatically set endpoint.")
                warning(f"Server endpoint set to {options['endpoint']}: this might not be a public IP address!")
        options["wg_bin"] = os.path.abspath(options.get("wg_bin", run_os_command("whereis wg | tr ' ' '\n' | grep bin")
                                                        .output))
        options["wg_quick_bin"] = os.path.abspath(options.get("wg_quick_bin",
                                                              run_os_command("whereis wg-quick | tr ' ' '\n' | grep bin")
                                                              .output))
        options["iptables_bin"] = os.path.abspath(options.get("iptables_bin",
                                                              run_os_command("whereis iptables | tr ' ' '\n' | grep bin")
                                                              .output))
        options["interfaces_folder"] = os.path.abspath(options.get("interfaces_folder",
                                                                   os.path.join(os.path.dirname(self.filepath),
                                                                                "interfaces")))
        try_makedir(options["interfaces_folder"])
        options["interfaces"] = options.get("interfaces", OrderedDict())
        interfaces = options["interfaces"]
        for iface in interfaces.values():
            iface = Interface.from_dict(iface)
            iface.wg_quick_bin = options["wg_quick_bin"]
            iface.gw_iface = options["gw_iface"]
            iface.conf_file = os.path.join(options["interfaces_folder"], iface.name) + ".conf"
            interfaces[iface.uuid] = iface
            for peer in iface.peers.values():
                peer.endpoint = options["endpoint"]
            iface.save()

    def __to_yaml_dict__(self):
        copy = super().__to_yaml_dict__()
        copy["linguard"]["interfaces"] = dict(copy["linguard"]["interfaces"])
        return copy


@yaml_info(yaml_tag_ns='')
class VersionInfo(BaseConfig):
    optional = True

    def __set_properties__(self):
        options = self.config.get("version", {})
        self.version = options.get("version", "")
        self.date = options.get("date", "")
        self.commit = options.get("commit", "")

    def save(self):
        raise WireguardError("Unable to update version info.")

