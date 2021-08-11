import os
from collections import OrderedDict
from random import randint
from time import sleep
from typing import Union, List
from uuid import uuid4 as gen_uuid

from coolname import generate_slug

from core.config.linguard_config import config
from core.models import Interface, interfaces
from core.modules.key_manager import KeyManager
from core.utils import get_default_gateway
from web.utils import fake


class InterfaceManager:

    def __init__(self, key_manager: KeyManager):
        self.key_manager = key_manager

    @staticmethod
    def is_port_in_use(port: int) -> bool:
        for iface in interfaces.values():
            if port == iface.listen_port:
                return True
        return False

    @staticmethod
    def sort_ifaces():
        sorted_ifaces = OrderedDict(sorted(interfaces.items(), key=lambda t: t[1].name))
        interfaces.clear()
        for uuid in sorted_ifaces:
            iface = sorted_ifaces[uuid]
            interfaces[uuid] = iface

    def add_iface(self, iface: Interface):
        interfaces[iface.uuid] = iface
        self.sort_ifaces()

    def generate_interface(self) -> Interface:
        uuid = gen_uuid().hex
        name = generate_slug(2)[:Interface.MAX_NAME_LENGTH]
        description = ""
        mask = f"/{randint(8, 30)}"
        ipv4_address = fake.ipv4_private() + mask
        port = randint(Interface.MIN_PORT_NUMBER, Interface.MAX_PORT_NUMBER)
        while self.is_port_in_use(port):
            port = randint(Interface.MIN_PORT_NUMBER, Interface.MAX_PORT_NUMBER)
        conf_file = os.path.join(config.interfaces_folder, name) + ".conf"
        private_key = self.key_manager.generate_privkey()
        public_key = self.key_manager.generate_pubkey(private_key)
        gw_iface = get_default_gateway()
        auto = True
        iface = Interface(uuid, name, conf_file, description, gw_iface, ipv4_address,
                          port, private_key, public_key, config.wg_quick_bin, auto)
        self.__set_iface_rules__(iface)

        return iface

    def remove_interface(self, iface: Union[Interface, str]):
        iface_to_remove = iface
        remove = True
        if iface_to_remove in interfaces:
            iface_to_remove = interfaces[iface]
        elif iface not in interfaces.values():
            remove = False
        if not remove:
            return False
        self.iface_down(iface_to_remove)
        if os.path.exists(iface_to_remove.conf_file):
            os.remove(iface_to_remove.conf_file)
        del interfaces[iface_to_remove.uuid]
        self.sort_ifaces()

    @staticmethod
    def __set_iface_rules__(iface: Interface):
        iface.on_up.append(f"{config.iptables_bin} -I FORWARD -i {iface.name} -j ACCEPT")
        iface.on_up.append(f"{config.iptables_bin} -I FORWARD -o {iface.name} -j ACCEPT")
        iface.on_up.append(f"{config.iptables_bin} -t nat -I POSTROUTING -o {iface.gw_iface} -j MASQUERADE")

        iface.on_down.append(f"{config.iptables_bin} -D FORWARD -i {iface.name} -j ACCEPT")
        iface.on_down.append(f"{config.iptables_bin} -D FORWARD -o {iface.name} -j ACCEPT")
        iface.on_down.append(f"{config.iptables_bin} -t nat -D POSTROUTING -o {iface.gw_iface} -j MASQUERADE")

    @staticmethod
    def edit_interface(iface: Interface, name: str, description: str, ipv4_address: str,
                       port: int, gw_iface: str, auto: bool, on_up: List[str], on_down: List[str]):
        iface.name = name
        iface.gw_iface = gw_iface
        iface.description = description
        iface.ipv4_address = ipv4_address
        iface.listen_port = port
        iface.auto = auto
        iface.on_up = on_up
        iface.on_down = on_down
        iface.conf_file = f"{os.path.join(config.interfaces_folder, iface.name)}.conf"

    def regenerate_keys(self, iface: Union[Interface, str]):
        privkey = self.key_manager.generate_privkey()
        pubkey = self.key_manager.generate_pubkey(privkey)
        if iface in interfaces:
            interfaces[iface].private_key = privkey
            interfaces[iface].public_key = pubkey
        if iface in interfaces.values():
            iface.private_key = privkey
            iface.public_key = pubkey

    @staticmethod
    def iface_up(iface: Union[Interface, str]):
        if iface in interfaces:
            interfaces[iface].up()
        if iface in interfaces.values():
            iface.up()

    @staticmethod
    def iface_down(iface: Union[Interface, str]):
        if iface in interfaces:
            interfaces[iface].down()
        if iface in interfaces.values():
            iface.down()

    @staticmethod
    def save_iface(iface: Union[Interface, str]):
        if iface in interfaces:
            interfaces[iface].save()
        if iface in interfaces.values():
            iface.save()

    def apply_iface(self, iface: Union[Interface, str]):
        self.iface_down(iface)
        self.save_iface(iface)
        self.iface_up(iface)

    def restart_iface(self, iface: Union[Interface, str]):
        self.iface_down(iface)
        sleep(1)
        self.iface_up(iface)
