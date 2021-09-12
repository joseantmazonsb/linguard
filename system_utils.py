import json
import os
import traceback
from logging import debug, error, fatal
from subprocess import run, PIPE
from typing import Dict, Any, List

from web.static.assets.resources import EMPTY_FIELD


def write_lines(content: str, path: str):
    with open(path, "w") as file:
        file.writelines(content)


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

    :param command:
    """
    proc = run(command, shell=True, check=False, stdout=PIPE, stderr=PIPE)
    debug(f"Running command '{command}'...")
    result = CommandResult(proc.returncode, proc.stdout.decode('utf-8').strip(), proc.stderr.decode('utf-8').strip())
    if not result.successful:
        error(f"Failed to run command '{command}': err={result.err} | out={result.output} | code={result.code}")
    return result


def run_tool(name: str) -> CommandResult:
    """
    Execute a core tool.

    :param name: Filename of the tool.
    :return:
    """
    bin_path = os.path.join(os.path.dirname(__file__), "core", "tools", name)
    return run_os_command(bin_path)


def get_system_interfaces() -> Dict[str, Any]:
    ifaces = {}
    for iface in json.loads(run_os_command("ip -json address").output):
        ifaces[iface["ifname"]] = iface
    return ifaces


def get_default_gateway() -> str:
    return run_os_command("ip route | head -1 | xargs | cut -d ' ' -f 5").output


def get_filename_without_extension(path: str) -> str:
    filename, extension = os.path.splitext(path)
    return os.path.basename(filename)


def try_makedir(path: str):
    try:
        os.makedirs(path)
        debug(f"Created folder ({path})...")
    except FileExistsError:
        pass
    except Exception as e:
        error(f"Unable to create folder: {e}.")
        raise


def log_exception(e: Exception, is_fatal: bool = False):
    error_msg = str(e) or f"{e.__class__.__name__} exception thrown by {e.__class__.__module__}"
    if is_fatal:
        fatal(error_msg)
    else:
        error(error_msg)
    debug(f"{traceback.format_exc()}")


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


def get_wg_interface_status(wg_bin: str, name: str) -> str:
    if run_os_command(f"sudo {wg_bin} show {name}").successful:
        return "up"
    return "down"


def list_to_str(_list: list, separator=", ") -> str:
    length = len(_list)
    text = ""
    count = 0
    for item in _list:
        if count < length - 1:
            text += item + separator
        else:
            text += item
        count += 1
    return text


def str_to_list(string: str, separator: str = "\n") -> List[str]:
    chunks = string.strip().split(separator)
    lst = []
    for cmd in chunks:
        lst.append(cmd)
    return lst
