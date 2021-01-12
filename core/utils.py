import yaml
import os
from subprocess import run, PIPE
from typing import Any, IO

#################
# Serialization #
#################


def yaml_dump(obj: Any, file: IO[str]):
    yaml.dump(obj, fp=file, default=lambda o: o.__dict__)


def yaml_dumps(obj: Any) -> str:
    return yaml.dumps(obj, default=lambda o: o.__dict__)

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
        command (object): Command to be executed.
    """
    proc = run(command, shell=True, check=False, stdout=PIPE, stderr=PIPE)
    result = CommandResult(proc.returncode, proc.stdout.decode('utf-8').strip(), proc.stderr.decode('utf-8').strip())
    return result


def get_filename_without_extension(path: str) -> str:
    filename, extension = os.path.splitext(path)
    return os.path.basename(filename)
