import os
from time import sleep

from coolname import generate_slug

from collections import OrderedDict
from random import randint
from typing import Dict, Union, List
from uuid import uuid4 as gen_uuid

from faker import Faker

from core.modules.key_manager import KeyManager
from core.wireguard import Interface


class InterfaceManager:

    def __init__(self, interfaces: Dict[str, Interface], key_manager: KeyManager, interfaces_folder: str,
                 iptables_bin: str, wg_quick_bin: str, gw_iface: str, faker: Faker):
        self.interfaces = interfaces
        self.key_manager = key_manager
        self.interfaces_folder = interfaces_folder
        self.iptables_bin = iptables_bin
        self.wg_quick_bin = wg_quick_bin
        self.gw_iface = gw_iface
        self.faker = faker

    def is_port_in_use(self, port: int) -> bool:
        for iface in self.interfaces.values():
            if port == iface.listen_port:
                return True
        return False

    def sort_ifaces(self):
        sorted_ifaces = OrderedDict(sorted(self.interfaces.items(), key=lambda t: t[1].name,))
        self.interfaces.clear()
        for uuid in sorted_ifaces:
            iface = sorted_ifaces[uuid]
            self.interfaces[uuid] = iface

    def add_iface(self, iface: Interface):
        self.interfaces[iface.uuid] = iface
        self.sort_ifaces()

    def generate_interface(self) -> Interface:
        uuid = gen_uuid().hex
        name = generate_slug(2)[:Interface.MAX_NAME_LENGTH]
        description = ""
        mask = f"/{randint(8, 30)}"
        ipv4_address = self.faker.ipv4_private() + mask
        port = randint(Interface.MIN_PORT_NUMBER, Interface.MAX_PORT_NUMBER)
        while self.is_port_in_use(port):
            port = randint(Interface.MIN_PORT_NUMBER, Interface.MAX_PORT_NUMBER)
        conf_file = os.path.join(self.interfaces_folder, name) + ".conf"
        private_key = self.key_manager.generate_privkey()
        public_key = self.key_manager.generate_pubkey(private_key)
        gw_iface = self.gw_iface
        auto = True
        iface = Interface(uuid, name, conf_file, description, gw_iface, ipv4_address,
                          port, private_key, public_key, self.wg_quick_bin, auto)
        self.__set_iface_rules__(iface)

        return iface

    def remove_interface(self, iface: Union[Interface, str]):
        iface_to_remove = iface
        remove = True
        if iface_to_remove in self.interfaces:
            iface_to_remove = self.interfaces[iface]
        elif iface not in self.interfaces.values():
            remove = False
        if not remove:
            return False
        self.iface_down(iface_to_remove)
        if os.path.exists(iface_to_remove.conf_file):
            os.remove(iface_to_remove.conf_file)
        del self.interfaces[iface_to_remove.uuid]
        self.sort_ifaces()

    def __set_iface_rules__(self, iface: Interface):
        iface.on_up.append(f"{self.iptables_bin} -I FORWARD -i {iface.name} -j ACCEPT")
        iface.on_up.append(f"{self.iptables_bin} -I FORWARD -o {iface.name} -j ACCEPT")
        iface.on_up.append(f"{self.iptables_bin} -t nat -I POSTROUTING -o {iface.gw_iface} -j MASQUERADE")

        iface.on_down.append(f"{self.iptables_bin} -D FORWARD -i {iface.name} -j ACCEPT")
        iface.on_down.append(f"{self.iptables_bin} -D FORWARD -o {iface.name} -j ACCEPT")
        iface.on_down.append(f"{self.iptables_bin} -t nat -D POSTROUTING -o {iface.gw_iface} -j MASQUERADE")

    def edit_interface(self, iface: Interface, name: str, description: str, ipv4_address: str,
                       port: int, gw_iface: str, auto: bool, on_up: List[str], on_down: List[str]):
        iface.name = name
        iface.gw_iface = gw_iface
        iface.description = description
        iface.ipv4_address = ipv4_address
        iface.listen_port = port
        iface.auto = auto
        iface.on_up = on_up
        iface.on_down = on_down
        if os.path.exists(iface.conf_file):
            os.remove(iface.conf_file)
        iface.conf_file = f"{os.path.join(self.interfaces_folder, iface.name)}.conf"

    def regenerate_keys(self, iface: Union[Interface, str]):
        privkey = self.key_manager.generate_privkey()
        pubkey = self.key_manager.generate_pubkey(privkey)
        if iface in self.interfaces:
            self.interfaces[iface].private_key = privkey
            self.interfaces[iface].public_key = pubkey
        if iface in self.interfaces.values():
            iface.private_key = privkey
            iface.public_key = pubkey

    def iface_up(self, iface: Union[Interface, str]):
        if iface in self.interfaces:
            self.interfaces[iface].up()
        if iface in self.interfaces.values():
            iface.up()

    def iface_down(self, iface: Union[Interface, str]):
        if iface in self.interfaces:
            self.interfaces[iface].down()
        if iface in self.interfaces.values():
            iface.down()

    def save_iface(self, iface: Union[Interface, str]):
        if iface in self.interfaces:
            self.interfaces[iface].save()
        if iface in self.interfaces.values():
            iface.save()

    def apply_iface(self, iface: Union[Interface, str]):
        self.iface_down(iface)
        self.save_iface(iface)
        self.iface_up(iface)

    def restart_iface(self, iface: Union[Interface, str]):
        self.iface_down(iface)
        sleep(1)
        self.iface_up(iface)