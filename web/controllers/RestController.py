import http
import io
import re
from http.client import NOT_FOUND
from logging import debug
from typing import Dict, Any, List

from flask import Response, send_file, url_for, redirect, abort
from flask_login import login_user

from core.app_manager import manager
from core.config.linguard_config import config as linguard_config, LinguardConfig
from core.config.logger_config import config as logger_config, LoggerConfig
from core.config.web_config import config as web_config, WebConfig
from core.exceptions import WireguardError
from core.models import Interface, Peer, interfaces
from core.utils import log_exception
from web.controllers.ViewController import ViewController
from web.models import users, User
from web.utils import get_system_interfaces

HTTP_NO_CONTENT = 204
HTTP_BAD_REQUEST = 400
HTTP_INTERNAL_ERROR = 500


class RestController:
    def regenerate_iface_keys(self) -> Response:
        try:
            manager.regenerate_keys(self.uuid)
            return Response(status=HTTP_NO_CONTENT)
        except WireguardError as e:
            log_exception(e)
            return Response(str(e), status=e.http_code)
        except Exception as e:
            log_exception(e)
            return Response(str(e), status=HTTP_INTERNAL_ERROR)

    def __init__(self, uuid: str = None):
        self.uuid = uuid

    def save_iface(self, data: Dict[str, Any]) -> Response:
        try:
            self.find_errors_in_save_iface(data)
            on_down = self.get_list_from_str(data["on_down"])
            on_up = self.get_list_from_str(data["on_up"])
            iface = interfaces[self.uuid]
            manager.edit_interface(iface, data["name"], data["description"],
                                   data["ipv4_address"], data["listen_port"], data["gw_iface"],
                                   data["auto"], on_up, on_down)
            manager.save_changes()
            return Response(status=HTTP_NO_CONTENT)
        except WireguardError as e:
            log_exception(e)
            return Response(str(e), status=e.http_code)
        except Exception as e:
            log_exception(e)
            return Response(str(e), status=HTTP_INTERNAL_ERROR)

    @staticmethod
    def get_list_from_str(string: str, separator: str = "\n") -> List[str]:
        chunks = string.strip().split(separator)
        lst = []
        for cmd in chunks:
            lst.append(cmd)
        return lst

    @staticmethod
    def find_errors_in_save_iface(data: Dict[str, Any]):
        if not re.match(Interface.REGEX_NAME, data["name"]):
            raise WireguardError("interface name can only contain alphanumeric characters, "
                                 "underscores (_) and hyphens (-). It must also begin with a "
                                 f"letter and cannot exceed {Interface.MAX_NAME_LENGTH} characters.", HTTP_BAD_REQUEST)
        if not re.match(Interface.REGEX_IPV4_CIDR, data["ipv4_address"]):
            raise WireguardError("invalid IPv4 address or mask. Must follow the format X.X.X.X/Y, "
                                 "just like 10.0.0.10/24, for instance.", HTTP_BAD_REQUEST)
        err_msg = f"listen port must be an integer between {Interface.MIN_PORT_NUMBER} " \
                  f"and {Interface.MAX_PORT_NUMBER} (both included)"
        try:
            port = int(data["listen_port"])
            if port < Interface.MIN_PORT_NUMBER or port > Interface.MAX_PORT_NUMBER:
                raise WireguardError(err_msg, HTTP_BAD_REQUEST)
        except Exception:
            raise WireguardError(err_msg, HTTP_BAD_REQUEST)
        gw_iface = data["gw_iface"]
        if not gw_iface:
            raise WireguardError(f"A valid gateway device must be provided,.", HTTP_BAD_REQUEST)
        if gw_iface not in get_system_interfaces():
            raise WireguardError(f"'{data['gw_iface']}' is not a valid gateway device.", HTTP_BAD_REQUEST)

    def apply_iface(self, data: Dict[str, Any]) -> Response:
        try:
            self.save_iface(data)
            iface = interfaces[self.uuid]
            manager.apply_iface(iface)
            return Response(status=HTTP_NO_CONTENT)
        except WireguardError as e:
            log_exception(e)
            return Response(str(e), status=e.http_code)
        except Exception as e:
            log_exception(e)
            return Response(str(e), status=HTTP_INTERNAL_ERROR)

    def add_iface(self, data: Dict[str, Any]) -> Response:
        try:
            self.find_errors_in_save_iface(data)
            iface = manager.pending_interfaces[self.uuid]
            on_up = self.get_list_from_str(data["on_up"])
            on_down = self.get_list_from_str(data["on_down"])
            manager.edit_interface(iface, data["name"], data["description"],
                                   data["ipv4_address"], data["listen_port"], data["gw_iface"],
                                   data["auto"], on_up, on_down)
            manager.add_iface(iface)
            manager.save_changes()
            return Response(status=HTTP_NO_CONTENT)
        except WireguardError as e:
            log_exception(e)
            return Response(str(e), status=e.http_code)
        except Exception as e:
            log_exception(e)
            return Response(str(e), status=HTTP_INTERNAL_ERROR)

    def remove_iface(self) -> Response:
        try:
            manager.remove_interface(self.uuid)
            manager.save_changes()
            return Response(status=HTTP_NO_CONTENT)
        except WireguardError as e:
            log_exception(e)
            return Response(str(e), status=e.http_code)
        except Exception as e:
            log_exception(e)
            return Response(str(e), status=HTTP_INTERNAL_ERROR)

    @staticmethod
    def find_errors_in_save_peer(data: Dict[str, Any]):
        wg_iface = data["interface"]
        if not wg_iface:
            raise WireguardError(f"a valid wireguard interface must be provided,.", HTTP_BAD_REQUEST)
        try:
            interfaces[wg_iface]
        except WireguardError:
            raise WireguardError(f"'{wg_iface}' is not a valid wireguard interface.", HTTP_BAD_REQUEST)
        if not re.match(Peer.REGEX_NAME, data["name"]):
            raise WireguardError("peer name can only contain alphanumeric characters, "
                                 "underscores (_), hyphens (-) and dots (.). It must also begin with a letter "
                                 f"and its length cannot exceed {Peer.MAX_NAME_LENGTH} characters.", HTTP_BAD_REQUEST)
        if not re.match(Interface.REGEX_IPV4_CIDR, data["ipv4_address"]):
            raise WireguardError("invalid IPv4 address or mask. Must follow the format X.X.X.X/Y, "
                                 "just like 10.0.0.10/24, for instance.", HTTP_BAD_REQUEST)
        if not re.match(Interface.REGEX_IPV4, data["dns1"]):
            raise WireguardError("invalid primary DNS. Must follow the format X.X.X.X, "
                                 "just like 8.8.8.8, for instance.", HTTP_BAD_REQUEST)
        if data["dns2"] and not re.match(Interface.REGEX_IPV4, data["dns2"]):
            raise WireguardError("invalid secondary DNS. Must follow the format X.X.X.X, "
                                 "just like 8.8.4.4, for instance.", HTTP_BAD_REQUEST)

    def add_peer(self, data: Dict[str, Any]) -> Response:
        try:
            self.find_errors_in_save_peer(data)
            iface = interfaces[data["interface"]]
            peer = manager.get_pending_peer_by_name(data["name"])
            manager.edit_peer(peer, data["name"], data["description"], data["ipv4_address"], iface,
                              data["dns1"], data["nat"], data.get("dns2", ""))
            manager.add_peer(peer)
            manager.save_changes()
            return Response(status=HTTP_NO_CONTENT)
        except WireguardError as e:
            log_exception(e)
            return Response(str(e), status=e.http_code)
        except Exception as e:
            log_exception(e)
            return Response(str(e), status=HTTP_INTERNAL_ERROR)

    @staticmethod
    def remove_peer(uuid: str) -> Response:
        try:
            peer = None
            for iface in interfaces.values():
                if uuid in iface.peers:
                    peer = iface.peers[uuid]
            if peer is None:
                raise WireguardError("unable to remove interface.", HTTP_BAD_REQUEST)
            manager.remove_peer(peer)
            manager.save_changes()
            return Response(status=HTTP_NO_CONTENT)
        except WireguardError as e:
            log_exception(e)
            return Response(str(e), status=e.http_code)
        except Exception as e:
            log_exception(e)
            return Response(str(e), status=HTTP_INTERNAL_ERROR)

    def save_peer(self, data: Dict[str, Any]) -> Response:
        try:
            peer = None
            for iface in interfaces.values():
                if self.uuid in iface.peers:
                    peer = iface.peers[self.uuid]
            if not peer:
                raise WireguardError(f"Unknown peer '{self.uuid}'.", NOT_FOUND)
            self.find_errors_in_save_peer(data)
            iface = interfaces[data["interface"]]
            manager.edit_peer(peer, data["name"], data["description"],
                              data["ipv4_address"], iface, data["dns1"],
                              data["nat"], data["dns2"])
            manager.save_changes()
            return Response(status=HTTP_NO_CONTENT)
        except WireguardError as e:
            log_exception(e)
            return Response(str(e), status=e.http_code)
        except Exception as e:
            log_exception(e)
            return Response(str(e), status=HTTP_INTERNAL_ERROR)

    def download_peer(self) -> Response:
        try:
            peer = None
            for iface in interfaces.values():
                if self.uuid in iface.peers:
                    peer = iface.peers[self.uuid]
            if not peer:
                raise WireguardError(f"Unknown peer '{self.uuid}'.", NOT_FOUND)
            conf = peer.generate_conf()
            proxy = io.StringIO()
            proxy.writelines(conf)
            # Creating the byteIO object from the StringIO Object
            mem = io.BytesIO()
            mem.write(proxy.getvalue().encode())
            # seeking was necessary. Python 3.5.2, Flask 0.12.2
            mem.seek(0)
            proxy.close()
            return send_file(mem, as_attachment=True, attachment_filename=f"{peer.name}.conf", mimetype="text/plain")
        except WireguardError as e:
            log_exception(e)
            return Response(str(e), status=e.http_code)
        except Exception as e:
            log_exception(e)
            return Response(str(e), status=HTTP_INTERNAL_ERROR)

    @staticmethod
    def save_settings(form):
        sample_logger = LoggerConfig()

        logger_config.logfile = form.log_file.data or sample_logger.logfile
        logger_config.overwrite = form.log_overwrite.data == "Yes" or sample_logger.overwrite
        logger_config.level = form.log_level.data or sample_logger.level

        sample_web = WebConfig()

        web_config.bindport = form.web_port.data or sample_web.bindport
        web_config.login_attempts = form.web_login_attempts.data or sample_web.login_attempts
        web_config.secret_key = form.web_secret_key.data or sample_web.secret_key
        web_config.credentials_file = form.web_credentials_file.data or sample_web.credentials_file

        sample_linguard = LinguardConfig()

        linguard_config.endpoint = form.app_endpoint.data or sample_linguard.endpoint
        linguard_config.wg_bin = form.app_wg_bin.data or sample_linguard.wg_bin
        linguard_config.wg_quick_bin = form.app_wg_quick_bin.data or sample_linguard.wg_quick_bin
        linguard_config.iptables_bin = form.app_iptables_bin.data or sample_linguard.iptables_bin
        linguard_config.interfaces_folder = form.app_interfaces_folder.data or sample_linguard.interfaces_folder

        manager.save_changes()

    @staticmethod
    def signup(form):
        if not form.validate():
            context = {
                "title": "Create admin account",
                "form": form
            }
            return ViewController("web/signup.html", **context).load()
        debug(f"Signing up user '{form.username.data}'...")
        u = User(form.username.data)
        u.password = form.password.data
        users[u.id] = u
        users.save(web_config.credentials_file, web_config.secret_key)
        debug(f"Logging in user '{u.id}'...")

        if u.login(form.password.data) and login_user(u):
            return redirect(form.next.data or url_for("router.index"))
        abort(http.HTTPStatus.INTERNAL_SERVER_ERROR)
