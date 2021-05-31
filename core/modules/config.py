import os
from collections import OrderedDict
from datetime import datetime
from http.client import BAD_REQUEST
from logging import info, warning, error
from typing import Dict

import yaml
from yamlable import YamlAble, yaml_info

from core.exceptions import WireguardError
from core.utils import run_os_command, try_makedirs
from core.wireguard import Interface

# Show no tags when serializing
yaml.emitter.Emitter.process_tag = lambda self, *args, **kw: None


@yaml_info(yaml_tag_ns='')
class Config(YamlAble):
    interfaces: Dict[str, Interface]

    def __init__(self, conf_file: str, backup_folder: str, interfaces_folder: str, wg_bin: str, wg_quick_bin: str,
                 iptables_bin: str, gw_iface: str, endpoint: str):
        self.conf_filepath = conf_file
        self.conf_filename = os.path.basename(conf_file)
        self.backup_folder = backup_folder
        self.interfaces_folder = interfaces_folder
        self.wg_bin = wg_bin
        self.wg_quick_bin = wg_quick_bin
        self.iptables_bin = iptables_bin
        self.gw_iface = gw_iface
        self.endpoint = endpoint

        try_makedirs(backup_folder)
        try_makedirs(interfaces_folder)

        self.interfaces = OrderedDict()

    def __to_yaml_dict__(self):
        """ Called when you call yaml.dump()"""
        return {
            "endpoint": self.endpoint,
            "wg_bin": self.wg_bin,
            "wg_quick_bin": self.wg_quick_bin,
            "iptables_bin": self.iptables_bin,
            "interfaces": dict(self.interfaces)
        }

    def __from_dict__(self, config: dict):
        self.endpoint = config["endpoint"]
        self.wg_bin = config["wg_bin"]
        self.wg_quick_bin = config["wg_quick_bin"]
        self.iptables_bin = config["iptables_bin"]
        self.interfaces.clear()
        interfaces = config["interfaces"]
        for iface in interfaces.values():
            iface = Interface.from_dict(iface)
            iface.wg_quick_bin = self.wg_quick_bin
            iface.gw_iface = self.gw_iface
            iface.conf_filepath = os.path.join(self.interfaces_folder, iface.name) + ".conf"
            self.interfaces[iface.uuid] = iface

    def save(self):
        """Write configuration to yaml file."""
        info("Saving current configuration...")
        with open(self.conf_filepath, 'w') as file:
            yaml.safe_dump(self, file, sort_keys=False)
        info("Current configuration saved successfully.")

    def load(self):
        try:
            info("Loading configuration...")
            self.load_backup(self.conf_filepath)
        except WireguardError:
            warning("No configuration file found. Starting fresh...")

    def backup(self):
        """Back up current configuration by copying the yaml file."""
        info("Backing up current configuration...")
        if not os.path.isfile(self.conf_filepath):
            warning("Unable to create backup. No configuration file exist.")
            return
        backup_file = f"{self.backup_folder}/{self.conf_filename}.bak{datetime.now().strftime('%Y%m%d%H%M%S')}"
        result = run_os_command(f"cp {self.conf_filepath} {backup_file}")
        if not result.successful:
            error(f"Failed to create backup: code={result.code} | err={result.err} | out={result.output}")
            return
        info("Backup completed.")

    def load_latest_backup(self):
        file = os.path.join(self.backup_folder, run_os_command(f"ls -t {self.backup_folder} | head -1").output)
        self.load_backup(file)

    def load_backup(self, path: str):
        """Restore configuration from a previously backed up yaml file."""
        info("Restoring backup...")
        if not path:
            msg = "Unable to restore backup: no backup file specified."
            error(msg)
            raise WireguardError(msg, BAD_REQUEST)
        if not os.path.exists(path):
            msg = f"Unable to restore backup file {path}: not found."
            error(msg)
            raise WireguardError(msg, BAD_REQUEST)
        with open(path, "r") as backup:
            config = list(yaml.safe_load_all(backup))[0]
            self.__from_dict__(config)
            info("Backup restored.")
