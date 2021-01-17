import json
import os
from subprocess import run, PIPE
from typing import Dict, List

###########
# Network #
###########


def get_interfaces() -> List[Dict[str, str]]:
    empty = "<i>Not configured.<i>"
    interfaces = []
    out = json.loads(run_os_command("ip -j a").output)
    for item in out:
        iface = {
            "name": item["ifname"],
            "status": item["operstate"].lower(),
        }
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
        interfaces.append(iface)
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
    return run_os_command(f"{wg_bin} genkey").output


def generate_pubkey(wg_bin: str, privkey: str):
    return run_os_command(f"echo {privkey} | {wg_bin} pubkey").output


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


def run_os_command(command: str) -> CommandResult:
    """
    Execute a command on the operating system.
    Returns an object containing the output
    [Data Types] object
    Args:
        :param command:
        :param as_root:
    """
    proc = run(command, shell=True, check=False, stdout=PIPE, stderr=PIPE)
    result = CommandResult(proc.returncode, proc.stdout.decode('utf-8').strip(), proc.stderr.decode('utf-8').strip())
    return result


def get_filename_without_extension(path: str) -> str:
    filename, extension = os.path.splitext(path)
    return os.path.basename(filename)
