import http
import os
from collections import OrderedDict
from random import randint
from time import sleep
from typing import Union, List, Dict

from core.config.linguard_config import config
from core.exceptions import WireguardError
from core.models import Interface, interfaces
from core.utils import generate_pubkey, generate_privkey


def add_iface(iface: Interface):
    interfaces[iface.uuid] = iface
    interfaces.sort()


def remove_interface(iface: Union[Interface, str]):
    iface_to_remove = iface
    remove = True
    if iface_to_remove in interfaces:
        iface_to_remove = interfaces[iface]
    elif iface not in interfaces.values():
        remove = False
    if not remove:
        return False
    iface_down(iface_to_remove)
    if os.path.exists(iface_to_remove.conf_file):
        os.remove(iface_to_remove.conf_file)
    del interfaces[iface_to_remove.uuid]
    interfaces.sort()
    for peer in iface_to_remove.peers:
        from core.modules import peer_manager
        peer_manager.remove_peer(peer)
    return True


def __set_iface_rules__(iface: Interface):
    iface.on_up.append(f"{config.iptables_bin} -I FORWARD -i {iface.name} -j ACCEPT")
    iface.on_up.append(f"{config.iptables_bin} -I FORWARD -o {iface.name} -j ACCEPT")
    iface.on_up.append(f"{config.iptables_bin} -t nat -I POSTROUTING -o {iface.gw_iface} -j MASQUERADE")

    iface.on_down.append(f"{config.iptables_bin} -D FORWARD -i {iface.name} -j ACCEPT")
    iface.on_down.append(f"{config.iptables_bin} -D FORWARD -o {iface.name} -j ACCEPT")
    iface.on_down.append(f"{config.iptables_bin} -t nat -D POSTROUTING -o {iface.gw_iface} -j MASQUERADE")


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


def refresh_keys(iface: Union[Interface, str]):
    privkey = generate_privkey()
    pubkey = generate_pubkey(privkey)
    if iface in interfaces:
        interfaces[iface].private_key = privkey
        interfaces[iface].public_key = pubkey
    if iface in interfaces.values():
        iface.private_key = privkey
        iface.public_key = pubkey


def iface_up(iface: Union[Interface, str]):
    if iface in interfaces:
        interfaces[iface].up()
    if iface in interfaces.values():
        iface.up()


def iface_down(iface: Union[Interface, str]):
    if iface in interfaces:
        interfaces[iface].down()
    if iface in interfaces.values():
        iface.down()


def save_iface(iface: Union[Interface, str]):
    if iface in interfaces:
        interfaces[iface].save()
    if iface in interfaces.values():
        iface.save()


def apply_iface(iface: Union[Interface, str]):
    iface_down(iface)
    save_iface(iface)
    iface_up(iface)


def restart_iface(iface: Union[Interface, str]):
    iface_down(iface)
    sleep(1)
    iface_up(iface)


def get_unused_port():
    tries = 100
    for i in range(0, tries):
        port = randint(Interface.MIN_PORT_NUMBER, Interface.MAX_PORT_NUMBER)
        if not Interface.is_port_in_use(port):
            return port
    raise WireguardError(f"Unable to obtain a free port (tried {tries} times)", http.HTTPStatus.BAD_REQUEST)


pending_interfaces: Dict[str, Interface]
pending_interfaces = OrderedDict()
