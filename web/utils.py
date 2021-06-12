from datetime import datetime
from typing import Dict, Any, List
import json

from flask import templating

from core.utils import run_os_command
from core.wireguard import Interface
from web.static.assets.resources import APP_NAME, EMPTY_FIELD


def render_template(template_path: str, **variables: Any):
    context = {
        "app_name": APP_NAME,
        "year": datetime.now().strftime("%Y")
    }
    if variables:
        context.update(variables)
    return templating.render_template(template_path, **context)


########
# Misc #
########


def list_to_str(_list: list) -> str:
    length = len(_list)
    text = ""
    count = 0
    for item in _list:
        if count < length - 1:
            text += item + ", "
        else:
            text += item
        count += 1
    return text


###########
# Network #
###########


def get_all_interfaces(wg_bin: str, wg_interfaces: List[Interface]) -> Dict[str, Dict[str, Any]]:
    interfaces = get_system_interfaces()
    for iface in wg_interfaces:
        if iface.name not in interfaces:
            interfaces[iface.name] = {
                "uuid": iface.uuid,
                "name": iface.name,
                "status": "down",
                "ipv4": iface.ipv4_address,
                "ipv6": EMPTY_FIELD,
                "mac": EMPTY_FIELD,
                "flags": EMPTY_FIELD
            }
        else:
            if iface in wg_interfaces:
                interfaces[iface.name]["uuid"] = iface.uuid
            if interfaces[iface.name]["status"] == "unknown":
                wg_iface_up = run_os_command(f"sudo {wg_bin} show {iface.name}").successful
                if wg_iface_up:
                    interfaces[iface.name]["status"] = "up"
                else:
                    interfaces[iface.name]["status"] = "down"
        interfaces[iface.name]["editable"] = True

    return interfaces


def get_wg_interface_status(wg_bin: str, name: str) -> str:
    if run_os_command(f"sudo {wg_bin} show {name}").successful:
        return "up"
    return "down"


def get_system_interfaces() -> Dict[str, Dict[str, Any]]:
    interfaces = {}
    out = json.loads(run_os_command("ip -json address").output)
    for item in out:
        flag_list = list(filter(lambda flag: "UP" not in flag, item["flags"]))
        flags = list_to_str(flag_list)
        iface = {
            "name": item["ifname"],
            "flags": flags,
            "status": item["operstate"].lower()
        }
        if "LOOPBACK" in iface["flags"]:
            iface["status"] = "up"
        if "address" in item:
            iface["mac"] = item["address"]
        else:
            iface["mac"] = EMPTY_FIELD
        addr_info = item["addr_info"]
        if addr_info:
            ipv4_info = addr_info[0]
            iface["ipv4"] = f"{ipv4_info['local']}/{ipv4_info['prefixlen']}"
            if len(addr_info) > 1:
                ipv6_info = addr_info[1]
                iface["ipv6"] = f"{ipv6_info['local']}/{ipv6_info['prefixlen']}"
            else:
                iface["ipv6"] = EMPTY_FIELD
        else:
            iface["ipv4"] = EMPTY_FIELD
            iface["ipv6"] = EMPTY_FIELD
        interfaces[iface["name"]] = iface
    return interfaces


def get_routing_table() -> List[Dict[str, Any]]:
    table = json.loads(run_os_command("ip -json route").output)
    for entry in table:
        for key in entry:
            value = entry[key]
            if not value:
                entry[key] = EMPTY_FIELD
            elif isinstance(value, list):
                entry[key] = list_to_str(value)
    return table


#############
# Wireguard #
#############

def get_wg_interfaces_summary(wg_bin: str, interfaces: List[Interface]) -> Dict[str, Dict[str, Any]]:
    dct = {}
    for iface in interfaces:
        if run_os_command(f"sudo {wg_bin} show {iface.name}").successful:
            status = "up"
        else:
            status = "down"
        dct[iface.name] = {
            "uuid": iface.uuid,
            "auto": iface.auto,
            "name": iface.name,
            "description": iface.description,
            "ipv4": iface.ipv4_address,
            "port": iface.listen_port,
            "status": status,
            "peers": iface.peers,
        }
    return dct
