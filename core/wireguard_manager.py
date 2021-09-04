import signal
import sys
from logging import info, warning

from core.exceptions import WireguardError
from core.models import interfaces


class WireguardManager:

    def __init__(self):
        info("Setting up termination signal handlers...")
        signal.signal(signal.SIGINT, self.terminal_signal_handler)
        signal.signal(signal.SIGTERM, self.terminal_signal_handler)
        signal.signal(signal.SIGQUIT, self.terminal_signal_handler)

    def terminal_signal_handler(self, sig, frame):
        warning(f"Caught termination signal {sig}. Shutting down the application...")
        self.stop()
        sys.exit(0)

    def start(self):
        info("Starting VPN server...")
        for iface in interfaces.values():
            if not iface.auto:
                continue
            try:
                iface.up()
            except WireguardError:
                pass
        info("VPN server started.")

    def stop(self):
        info("Stopping VPN server...")
        for iface in interfaces.values():
            try:
                iface.down()
            except WireguardError:
                pass
        info("VPN server stopped.")


wireguard_manager = WireguardManager()
