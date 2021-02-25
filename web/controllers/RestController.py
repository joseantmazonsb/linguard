import re
from typing import Dict, Any, List

from flask import Response

from core.wireguard.exceptions import WireguardError
from core.wireguard.interface import Interface
from core.wireguard.server import Server
from web.utils import get_system_interfaces


HTTP_NO_CONTENT = 204
HTTP_BAD_REQUEST = 400
HTTP_INTERNAL_ERROR = 500


class RestController:
    def __init__(self, server: Server, uuid: str):
        self.server = server
        self.uuid = uuid

    def regenerate_iface_keys(self) -> Response:
        try:
            self.server.regenerate_keys(self.uuid)
            return Response(status=HTTP_NO_CONTENT)
        except WireguardError as e:
            return Response(str(e), status=e.http_code)
        except Exception as e:
            return Response(str(e), status=HTTP_INTERNAL_ERROR)

    def save_iface(self, data: Dict[str, Any]) -> Response:
        try:
            on_up = self.get_list_from_str(data["on_up"])
            on_down = self.get_list_from_str(data["on_down"])
            self.find_errors_in_save(data)
            iface = self.server.interfaces[self.uuid]
            self.server.edit_interface(iface, data["name"], data["description"],
                                       data["ipv4_address"], data["listen_port"], data["gw_iface"],
                                       data["auto"], on_up, on_down)
            self.server.save_changes()
            return Response(status=HTTP_NO_CONTENT)
        except WireguardError as e:
            return Response(str(e), status=e.http_code)
        except Exception as e:
            return Response(str(e), status=HTTP_INTERNAL_ERROR)

    @staticmethod
    def get_list_from_str(string: str, separator: str = "\n") -> List[str]:
        chunks = string.strip().split(separator)
        lst = []
        for cmd in chunks:
            lst.append(cmd)
        return lst

    @staticmethod
    def find_errors_in_save(data: Dict[str, Any]):
        if not re.match(Interface.REGEX_NAME, data["name"]):
            raise WireguardError("interface's name can only contain alphanumeric characters, "
                                 "underscores (_) and hyphens (-), and it must begin with a character.", HTTP_BAD_REQUEST)
        if not re.match(Interface.REGEX_IPV4, data["ipv4_address"]):
            raise WireguardError("invalid IPv4 address or mask. Must follow the format X.X.X.X/Y, "
                                 "just like 10.0.0.10/24.", HTTP_BAD_REQUEST)
        err_msg = f"listen port must be an integer between {Interface.MIN_PORT_NUMBER} " \
                  f"and {Interface.MAX_PORT_NUMBER} (both included)"
        try:
            port = int(data["listen_port"])
            if port < Interface.MIN_PORT_NUMBER or port > Interface.MAX_PORT_NUMBER:
                raise WireguardError(err_msg, HTTP_BAD_REQUEST)
        except Exception:
            raise WireguardError(err_msg, HTTP_BAD_REQUEST)
        if data["gw_iface"] not in get_system_interfaces():
            raise WireguardError(f"{data['gw_iface']} is not a valid gateway device.", HTTP_BAD_REQUEST)

    def apply_iface(self, data: Dict[str, Any]) -> Response:
        try:
            self.save_iface(data)
            self.server.apply_iface(self.uuid)
            return Response(status=HTTP_NO_CONTENT)
        except WireguardError as e:
            return Response(str(e), status=e.http_code)
        except Exception as e:
            return Response(str(e), status=HTTP_INTERNAL_ERROR)

    def add_iface(self, data: Dict[str, Any]) -> Response:
        try:
            self.find_errors_in_save(data)
            iface = self.server.interfaces[self.uuid]
            on_up = self.get_list_from_str(data["on_up"])
            on_down = self.get_list_from_str(data["on_down"])
            self.server.edit_interface(iface, data["name"], data["description"],
                                       data["ipv4_address"], data["listen_port"], data["gw_iface"],
                                       data["auto"], on_up, on_down)
            self.server.confirm_interface(iface)
            self.server.save_changes()
            return Response(status=HTTP_NO_CONTENT)
        except WireguardError as e:
            return Response(str(e), status=e.http_code)
        except Exception as e:
            return Response(str(e), status=HTTP_INTERNAL_ERROR)

    def remove_iface(self) -> Response:
        try:
            self.server.remove_interface(self.uuid)
            return Response(status=HTTP_NO_CONTENT)
        except WireguardError as e:
            return Response(str(e), status=e.http_code)
        except Exception as e:
            return Response(str(e), status=HTTP_INTERNAL_ERROR)
