import json
from typing import List, Dict, Any

from linguard.common.utils.strings import list_to_str
from linguard.common.utils.system import Command
from linguard.web.static.assets.resources import EMPTY_FIELD


def get_system_interfaces() -> Dict[str, Any]:
    ifaces = {}
    for iface in json.loads(Command("ip -json address").run().output):
        ifaces[iface["ifname"]] = iface
    return ifaces


def get_default_gateway() -> str:
    return Command("ip route | head -1 | xargs | cut -d ' ' -f 5").run().output


def get_routing_table() -> List[Dict[str, Any]]:
    table = json.loads(Command("ip -json route").run().output)
    for entry in table:
        for key in entry:
            value = entry[key]
            if not value:
                entry[key] = EMPTY_FIELD
            elif isinstance(value, list):
                entry[key] = list_to_str(value)
    return table
