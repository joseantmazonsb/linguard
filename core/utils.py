import json
import os
from subprocess import run, PIPE
from typing import Dict, Any


###########
# Network #
###########


def get_all_interfaces(wg_bin: str, wg_interfaces: list) -> Dict[str, Dict[str, Any]]:
    empty = "<i>Not configured.<i>"
    interfaces = get_system_interfaces(empty)
    for iface in wg_interfaces:
        if iface.name not in interfaces:
            interfaces[iface.name] = {
                "name": iface.name,
                "status": "down",
                "ipv4": iface.ipv4_address,
                "ipv6": empty,
                "mac": empty,
                "flags": empty
            }
        else:
            if interfaces[iface.name]["status"] == "unknown":
                wg_iface_up = run_os_command(f"{wg_bin} show {iface.name}", as_root=True).successful
                if wg_iface_up:
                    interfaces[iface.name]["status"] = "up"
                else:
                    interfaces[iface.name]["status"] = "down"
        interfaces[iface.name]["editable"] = True

    return interfaces


def get_system_interfaces(empty: str) -> Dict[str, Dict[str, Any]]:
    interfaces = {}
    out = json.loads(run_os_command("ip -json address").output)
    for item in out:
        flag_list = list(filter(lambda flag: "UP" not in flag, item["flags"]))
        flag_list_length = len(flag_list)
        flags = ""
        count = 0
        for flag in flag_list:
            if "UP" not in flag:
                if count < flag_list_length - 1:
                    flags += flag + ", "
                else:
                    flags += flag
            count += 1
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
            iface["mac"] = empty
        addr_info = item["addr_info"]
        if addr_info:
            ipv4_info = addr_info[0]
            iface["ipv4"] = f"{ipv4_info['local']}/{ipv4_info['prefixlen']}"
            if len(addr_info) > 1:
                ipv6_info = addr_info[1]
                iface["ipv6"] = f"{ipv6_info['local']}/{ipv6_info['prefixlen']}"
            else:
                iface["ipv6"] = empty
        else:
            iface["ipv4"] = empty
            iface["ipv6"] = empty
        interfaces[iface["name"]] = iface
    return interfaces

###########
# Storage #
###########


def write_lines(content: str, path: str):
    with open(path, "w") as file:
        file.writelines(content)

#############
# Wireguard #
#############


def generate_privkey(wg_bin: str):
    return run_os_command(f"{wg_bin} genkey", as_root=True).output


def generate_pubkey(wg_bin: str, privkey: str):
    return run_os_command(f"echo {privkey} | {wg_bin} pubkey", as_root=True).output


#####################
# System Operations #
#####################

class CommandResult:
    """Represents the result of an OS command's execution."""

    def __init__(self, code: int, output: str, err: str):
        self.code = code
        self.output = output
        self.err = err
        self.successful = (code < 1)


def run_os_command(command: str, as_root: bool = False) -> CommandResult:
    """
    Execute a command on the operating system.
    Returns an object containing the output
    [Data Types] object
    Args:
        :param command:
        :param as_root:
    """
    if as_root:
        cmd = f"sudo {command}"
    else:
        cmd = command
    proc = run(cmd, shell=True, check=False, stdout=PIPE, stderr=PIPE)
    result = CommandResult(proc.returncode, proc.stdout.decode('utf-8').strip(), proc.stderr.decode('utf-8').strip())
    return result


def get_filename_without_extension(path: str) -> str:
    filename, extension = os.path.splitext(path)
    return os.path.basename(filename)
