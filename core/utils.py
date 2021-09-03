from typing import List, Dict, Any

from core.config.linguard_config import config as linguard_config
from core.exceptions import WireguardError
from core.models import Interface
from system_utils import run_os_command


def is_wg_iface_up(iface_name: str) -> bool:
    return run_os_command(f"sudo {linguard_config.wg_bin} show {iface_name}").successful


def generate_privkey() -> str:
    result = run_os_command(f"sudo {linguard_config.wg_bin} genkey")
    if not result.successful:
        raise WireguardError(result.err)
    return result.output


def generate_pubkey(privkey: str) -> str:
    result = run_os_command(f"echo {privkey} | sudo {linguard_config.wg_bin} pubkey")
    if not result.successful:
        raise WireguardError(result.err)
    return result.output


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
