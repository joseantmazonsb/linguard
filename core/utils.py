import os
import traceback
from logging import debug, error, fatal
from subprocess import run, PIPE


###########
# Storage #
###########


def write_lines(content: str, path: str):
    with open(path, "w") as file:
        file.writelines(content)


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
    """
    proc = run(command, shell=True, check=False, stdout=PIPE, stderr=PIPE)
    result = CommandResult(proc.returncode, proc.stdout.decode('utf-8').strip(), proc.stderr.decode('utf-8').strip())
    return result


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


#############
# Wireguard #
#############


def generate_privkey(wg_bin: str) -> CommandResult:
    return run_os_command(f"sudo {wg_bin} genkey")


def generate_pubkey(wg_bin: str, privkey: str) -> CommandResult:
    return run_os_command(f"echo {privkey} | sudo {wg_bin} pubkey")
