from logging import info

from linguard.core.exceptions import WireguardError
from linguard.core.models import interfaces


class WireguardManager:

    @staticmethod
    def start():
        info("Starting VPN server...")
        for iface in interfaces.values():
            if not iface.auto:
                continue
            try:
                iface.up()
            except WireguardError:
                pass
        info("VPN server started.")

    @staticmethod
    def stop():
        info("Stopping VPN server...")
        for iface in interfaces.values():
            try:
                iface.down()
            except WireguardError:
                pass
        info("VPN server stopped.")


wireguard_manager = WireguardManager()
