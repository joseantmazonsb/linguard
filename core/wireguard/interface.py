from audioop import error
from logging import info

from core.utils import run_os_command


class Interface:

    def __init__(self, name: str, description: str, gw_iface: str, ipv4_address,
                 listen_port: int, private_key: str, public_key: str, wg_quick_bin: str):
        self.name = name
        self.gw_iface = gw_iface
        self.description = description
        self.ipv4_address = ipv4_address
        self.listen_port = listen_port
        self.wg_quick_bin = wg_quick_bin
        self.private_key = private_key
        self.public_key = public_key
        self.on_up = []
        self.on_down = []

    def up(self) -> bool:
        info(f"Starting interface {self.name}...")
        result = run_os_command(f"{self.wg_quick_bin} up {self.name}")
        if result.successful:
            info(f"Interface {self.name} started.")
        else:
            error(f"Failed to start interface {self.name}: code={result.code} | err={result.err} | out={result.output}")
        return result.successful

    def down(self) -> bool:
        info(f"Stopping interface {self.name}...")
        result = run_os_command(f"{self.wg_quick_bin} down {self.name}")
        if result.successful:
            info(f"Interface {self.name} stopped.")
        else:
            error(f"Failed to stop interface {self.name}: code={result.code} | err={result.err} | out={result.output}")
        return result.successful
