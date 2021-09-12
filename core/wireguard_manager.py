from logging import info

from core.exceptions import WireguardError
from core.models import interfaces


class WireguardManager:

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
