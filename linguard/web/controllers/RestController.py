import http
import io
import json
from http.client import NO_CONTENT, INTERNAL_SERVER_ERROR
from ipaddress import IPv4Interface
from logging import debug

from flask import Response, url_for, redirect, abort, request
from flask_login import login_user
from werkzeug.wsgi import FileWrapper

from linguard.common.models.user import users, User
from linguard.common.utils.logs import log_exception
from linguard.common.utils.strings import str_to_list
from linguard.core.config.logger import config as logger_config, LoggerConfig
from linguard.core.config.traffic import config as traffic_config
from linguard.core.config.web import config as web_config, WebConfig
from linguard.core.config.wireguard import config as wireguard_config, WireguardConfig
from linguard.core.exceptions import WireguardError
from linguard.core.managers import traffic_storage
from linguard.core.managers.config import config_manager
from linguard.core.models import Interface, Peer, interfaces
from linguard.web.controllers.ViewController import ViewController


class RestController:

    def __init__(self, uuid: str = ""):
        self.uuid = uuid

    @staticmethod
    def __save_iface__(iface: Interface, form):
        iface.edit(name=form.name.data, description=form.description.data,
                   gw_iface=form.gateway.data, ipv4_address=IPv4Interface(form.ipv4.data),
                   port=form.port.data, auto=form.auto.data, on_up=str_to_list(form.on_up.data),
                   on_down=str_to_list(form.on_down.data))
        config_manager.save()

    def apply_iface(self, iface: Interface, form):
        self.__save_iface__(iface, form)
        iface.apply()

    @staticmethod
    def add_iface(form):
        on_up = str_to_list(form.on_up.data)
        on_down = str_to_list(form.on_down.data)
        iface = Interface(name=form.name.data, description=form.description.data, gw_iface=form.gateway.data,
                          ipv4_address=form.ipv4.data, listen_port=form.port.data, auto=form.auto.data, on_up=on_up,
                          on_down=on_down)
        interfaces[iface.uuid] = iface
        interfaces.sort()
        config_manager.save()

    def remove_iface(self) -> Response:
        try:
            interfaces[self.uuid].remove()
            config_manager.save()
            return Response(status=NO_CONTENT)
        except WireguardError as e:
            log_exception(e)
            return Response(str(e), status=e.http_code)
        except Exception as e:
            log_exception(e)
            return Response(str(e), status=INTERNAL_SERVER_ERROR)

    @staticmethod
    def add_peer(form) -> Peer:
        iface = interfaces.get_value_by_attr("name", form.interface.data)
        peer = Peer(name=form.name.data, description=form.description.data,
                    interface=iface, ipv4_address=IPv4Interface(form.ipv4.data),
                    dns1=form.dns1.data, dns2=form.dns2.data, nat=form.nat.data)
        iface.add_peer(peer)
        config_manager.save()
        return peer

    @staticmethod
    def remove_peer(peer: Peer) -> Response:
        try:
            peer.remove()
            config_manager.save()
            return Response(status=NO_CONTENT)
        except Exception as e:
            log_exception(e)
            return Response(str(e), status=INTERNAL_SERVER_ERROR)

    @staticmethod
    def save_peer(peer: Peer, form):
        iface = interfaces.get_value_by_attr("name", form.interface.data)
        peer.edit(name=form.name.data, description=form.description.data, interface=iface,
                  ipv4_address=IPv4Interface(form.ipv4.data), nat=form.nat.data, dns1=form.dns1.data, dns2=form.dns2.data)
        config_manager.save()

    def download_peer(self, peer: Peer) -> Response:
        try:
            conf = peer.generate_conf()
            return self.send_text_as_file(filename=f"{peer.name}.conf", text=conf)
        except WireguardError as e:
            log_exception(e)
            return Response(str(e), status=e.http_code)
        except Exception as e:
            log_exception(e)
            return Response(str(e), status=INTERNAL_SERVER_ERROR)

    def download_iface(self, iface: Interface) -> Response:
        try:
            conf = iface.generate_conf()
            return self.send_text_as_file(filename=f"{iface.name}.conf", text=conf)
        except Exception as e:
            log_exception(e)
            return Response(str(e), status=INTERNAL_SERVER_ERROR)

    @staticmethod
    def send_text_as_file(filename: str, text: str):
        wrapper = FileWrapper(io.BytesIO(text.encode()))
        headers = {
            'Content-Disposition': f'attachment; filename={filename}'
        }
        return Response(wrapper, mimetype='text/plain', direct_passthrough=True, headers=headers)

    @staticmethod
    def save_settings(form):
        sample_logger = LoggerConfig()

        logger_config.overwrite = form.log_overwrite.data
        logger_config.level = form.log_level.data or sample_logger.level

        sample_web = WebConfig()

        web_config.login_attempts = form.web_login_attempts.data or sample_web.login_attempts
        web_config.login_ban_time = form.web_login_ban_time.data or sample_web.login_ban_time

        web_config.secret_key = form.web_secret_key.data or sample_web.secret_key

        sample_wireguard = WireguardConfig()

        wireguard_config.endpoint = form.app_endpoint.data or sample_wireguard.endpoint
        wireguard_config.wg_bin = form.app_wg_bin.data or sample_wireguard.wg_bin
        wireguard_config.wg_quick_bin = form.app_wg_quick_bin.data or sample_wireguard.wg_quick_bin
        wireguard_config.iptables_bin = form.app_iptables_bin.data or sample_wireguard.iptables_bin

        traffic_config.enabled = form.traffic_enabled.data
        driver_name = form.traffic_driver.data
        driver = traffic_storage.registered_drivers[driver_name]
        options = json.loads(form.traffic_driver_options.data.replace("\'", "\""))
        traffic_config.driver = driver.__from_yaml_dict__(options)

        config_manager.save()

    @staticmethod
    def apply_setup(form):
        logger_config.overwrite = form.log_overwrite.data

        sample_wireguard = WireguardConfig()

        wireguard_config.endpoint = form.app_endpoint.data or sample_wireguard.endpoint
        wireguard_config.wg_bin = form.app_wg_bin.data or sample_wireguard.wg_bin
        wireguard_config.wg_quick_bin = form.app_wg_quick_bin.data or sample_wireguard.wg_quick_bin
        wireguard_config.iptables_bin = form.app_iptables_bin.data or sample_wireguard.iptables_bin

        traffic_config.enabled = form.traffic_enabled.data

        config_manager.save()

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
            return redirect(url_for("router.setup", next=request.args.get("next", None)))
        abort(http.HTTPStatus.INTERNAL_SERVER_ERROR)

