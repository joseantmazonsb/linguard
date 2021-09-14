import os
from logging import debug, error
from subprocess import run, PIPE


class CommandResult:
    """Represents the result of a command execution."""

    def __init__(self, code: int, output: str, err: str):
        self.code = code
        self.output = output
        self.err = err
        self.successful = (code < 1)


class Command:
    """
    Represents an interface to interact with a binary, executable file.
    """

    def __init__(self, cmd):
        self.cmd = cmd

    def run(self, as_root: bool = False) -> CommandResult:
        """
        Execute the command and return information about the execution.
        :param as_root: Run the command as root (using sudo)
        :return: A CommandResult object containing information about how the execution went.
        """
        cmd = self.cmd
        if as_root:
            cmd = f"sudo {cmd}"
        debug(f"Running '{cmd}'...")
        proc = run(cmd, shell=True, check=False, stdout=PIPE, stderr=PIPE)
        result = CommandResult(proc.returncode, proc.stdout.decode('utf-8').strip(),
                               proc.stderr.decode('utf-8').strip())
        if not result.successful:
            error(f"Failed to run '{cmd}': err={result.err} | out={result.output} | code={result.code}")
        return result

    def run_as_root(self) -> CommandResult:
        return self.run(True)


def try_makedir(path: str):
    try:
        os.makedirs(path)
        debug(f"Created folder ({path})...")
    except FileExistsError:
        pass
    except Exception as e:
        error(f"Unable to create folder: {e}.")
        raise
