import os
from subprocess import run, PIPE

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
