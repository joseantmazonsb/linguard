import os

from linguard.common.utils.system import Command, CommandResult


def get_tools_folder():
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), "tools")


def get_tool_path(name: str):
    return os.path.join(get_tools_folder(), name)


def run_tool(name: str, as_root: bool = False) -> CommandResult:
    return Command(get_tool_path(name)).run(as_root)


def run_tool_as_root(name: str) -> CommandResult:
    return Command(get_tool_path(name)).run(True)
