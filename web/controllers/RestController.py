import re
from typing import Dict, Any

from flask import Response

from core.wireguard.exceptions import WireguardError
from core.wireguard.interface import Interface
from core.wireguard.server import Server
from web.utils import get_system_interfaces


HTTP_NO_CONTENT = 204
HTTP_BAD_REQUEST = 400
HTTP_INTERNAL_ERROR = 500


class RestController:
    def __init__(self, server: Server, iface: str):
        self.server = server
        self.iface = iface

    def regenerate_iface_keys(self) -> Response:
        try:
            self.server.regenerate_keys(self.iface)
            return Response(status=HTTP_NO_CONTENT)
        except WireguardError as e:
            return Response(str(e), status=e.http_code)
        except Exception as e:
            return Response(str(e), status=HTTP_INTERNAL_ERROR)

    def save_iface(self, data: Dict[str, Any]) -> Response:
        try:
            on_up_chunks = data["on_up"].strip().split("\n")
            on_up = []
            for cmd in on_up_chunks:
                on_up.append(cmd)
            data["on_up"] = on_up
            on_down_chunks = data["on_down"].strip().split("\n")
            on_down = []
            for cmd in on_down_chunks:
                on_down.append(cmd)
            data["on_down"] = on_down
            self.find_errors_in_save(data)
            self.server.edit_interface(self.iface, data["name"], data["description"],
                                       data["ipv4"], data["port"], data["gw"],
                                       data["on_up"], data["on_down"])
            self.server.save_changes()
            return Response(status=HTTP_NO_CONTENT)
        except WireguardError as e:
            return Response(str(e), status=e.http_code)
        except Exception as e:
            return Response(str(e), status=HTTP_INTERNAL_ERROR)

    @staticmethod
    def find_errors_in_save(data: Dict[str, Any]):
        if not re.match(Interface.REGEX_NAME, data["name"]):
            raise WireguardError("interface's name can only contain alphanumeric characters, "
                                 "underscores (_) and hyphens (-).", HTTP_BAD_REQUEST)
        if not re.match(Interface.REGEX_IPV4, data["ipv4"]):
            raise WireguardError("invalid IPv4 address or mask. Must follow the format X.X.X.X/Y, "
                                 "just like 10.0.0.10/24.", HTTP_BAD_REQUEST)
        err_msg = f"listen port must be an integer between {Interface.MIN_PORT_NUMBER} " \
                  f"and {Interface.MAX_PORT_NUMBER} (both included)"
        try:
            port = int(data["port"])
            if port < Interface.MIN_PORT_NUMBER or port > Interface.MAX_PORT_NUMBER:
                raise WireguardError(err_msg, HTTP_BAD_REQUEST)
        except Exception:
            raise WireguardError(err_msg, HTTP_BAD_REQUEST)
        if data["gw"] not in get_system_interfaces():
            raise WireguardError(f"{data['gw']} is not a valid gateway device.", HTTP_BAD_REQUEST)

    def apply_iface(self, data: Dict[str, Any]) -> Response:
        try:
            self.save_iface(data)
            self.server.apply_changes()
            return Response(status=HTTP_NO_CONTENT)
        except WireguardError as e:
            return Response(str(e), status=e.http_code)
        except Exception as e:
            return Response(str(e), status=HTTP_INTERNAL_ERROR)

    def add_iface(self, data: Dict[str, Any]) -> Response:
        return Response(status=HTTP_NO_CONTENT)
