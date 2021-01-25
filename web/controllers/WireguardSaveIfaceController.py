import re
from typing import Any, Dict

from flask import Response

from core.wireguard.exceptions import WireguardError
from core.wireguard.interface import Interface
from core.wireguard.server import Server
from web.controllers.RestController import RestController
from web.utils import get_system_interfaces


class WireguardSaveIfaceController(RestController):

    def __init__(self, server: Server, data: Dict[str, Any], name: str):
        super().__init__(server, data)
        self.name = name

    def serve(self) -> Response:
        on_up_chunks = self.data["on_up"].strip().split("\n")
        on_up = []
        for cmd in on_up_chunks:
            on_up.append(cmd)
        self.data["on_up"] = on_up
        on_down_chunks = self.data["on_down"].strip().split("\n")
        on_down = []
        for cmd in on_down_chunks:
            on_down.append(cmd)
        self.data["on_down"] = on_down
        self.find_errors()
        self.server.edit_interface(self.name, self.data["name"], self.data["description"],
                                   self.data["ipv4"], self.data["port"], self.data["gw"],
                                   self.data["on_up"], self.data["on_down"])
        return Response(status=204)

    def find_errors(self):
        if not re.match(Interface.REGEX_NAME, self.data["name"]):
            raise WireguardError("interface's name can only contain alphanumeric characters, "
                                 "underscores (_) and hyphens (-).", 400)
        if not re.match(Interface.REGEX_IPV4, self.data["ipv4"]):
            raise WireguardError("invalid IPv4 address or mask. Must follow the format X.X.X.X/Y, "
                                 "just like 10.0.0.10/24.", 400)
        err_msg = f"listen port must be between {Interface.MIN_PORT_NUMBER} " \
                  f"and {Interface.MAX_PORT_NUMBER} (both included)"
        try:
            port = int(self.data["port"])
            if port < Interface.MIN_PORT_NUMBER or port > Interface.MAX_PORT_NUMBER:
                raise WireguardError(err_msg, 400)
        except Exception:
            raise WireguardError(err_msg, 400)
        if self.data["gw"] not in get_system_interfaces():
            raise WireguardError(f"{self.data['gw']} is not a valid gateway device.", 400)
