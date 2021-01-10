from subprocess import run

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
    result = CommandResult(proc.returncode, proc.stdout.decode('utf-8'), proc.stderr.decode('utf-8'))
    return result
