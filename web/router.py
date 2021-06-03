from datetime import datetime
from http.client import BAD_REQUEST, NOT_FOUND, INTERNAL_SERVER_ERROR, UNAUTHORIZED, NO_CONTENT

from flask import Blueprint, abort, request, Response

from core.exceptions import WireguardError
from web.controllers.RestController import RestController
from web.controllers.ViewController import ViewController
from web.utils import get_all_interfaces, get_routing_table, get_wg_interfaces_summary, get_wg_interface_status
from core.server import Server
from web.static.assets.resources import EMPTY_FIELD, APP_NAME


class Router(Blueprint):
    server: Server

    def __init__(self, name, import_name):
        super().__init__(name, import_name)


router = Router("router", __name__)


@router.route("/")
@router.route("/dashboard")
def index():
    context = {
        "title": "Dashboard"
    }
    return ViewController("web/index.html", **context).load()


@router.route("/login")
def login():
    context = {
        "title": "Login"
    }
    return ViewController("web/login.html", **context).load()


@router.route("/signup")
def signup():
    context = {
        "title": "Sign up"
    }
    return ViewController("web/signup.html", **context).load()


@router.route("/network")
def network():
    wg_ifaces = list(router.server.interfaces.values())
    interfaces = get_all_interfaces(wg_bin=router.server.config.wg_bin, wg_interfaces=wg_ifaces)
    routes = get_routing_table()
    context = {
        "title": "Network",
        "interfaces": interfaces,
        "routes": routes,
        "last_update": datetime.now().strftime("%H:%M"),
        "EMPTY_FIELD": EMPTY_FIELD
    }
    return ViewController("web/network.html", **context).load()


@router.route("/wireguard")
def wireguard():
    wg_ifaces = list(router.server.interfaces.values())
    interfaces = get_wg_interfaces_summary(wg_bin=router.server.config.wg_bin, interfaces=wg_ifaces)
    context = {
        "title": "Wireguard",
        "interfaces": interfaces,
        "last_update": datetime.now().strftime("%H:%M"),
        "EMPTY_FIELD": EMPTY_FIELD
    }
    return ViewController("web/wireguard.html", **context).load()


@router.route("/wireguard/interfaces/add",  methods=['GET'])
def create_wireguard_iface():
    iface = router.server.generate_interface()
    context = {
        "title": "Add interface",
        "iface": iface,
        "EMPTY_FIELD": EMPTY_FIELD,
        "APP_NAME": APP_NAME
    }
    return ViewController("web/wireguard-add-iface.html", **context).load()


@router.route("/wireguard/interfaces/add/<uuid>",  methods=['POST'])
def add_wireguard_iface(uuid: str):
    data = request.json["data"]
    return RestController(router.server, uuid).add_iface(data)


@router.route("/wireguard/interfaces/<uuid>",  methods=['GET'])
def get_wireguard_iface(uuid: str):
    if uuid not in router.server.interfaces:
        abort(NOT_FOUND, f"Unknown interface '{uuid}'.")
    iface = router.server.interfaces[uuid]
    iface_status = get_wg_interface_status(router.server.config.wg_bin, iface.name)
    context = {
        "title": "Edit interface",
        "iface": iface,
        "iface_status": iface_status,
        "last_update": datetime.now().strftime("%H:%M"),
        "EMPTY_FIELD": EMPTY_FIELD,
        "APP_NAME": APP_NAME
    }
    return ViewController("web/wireguard-iface.html", **context).load()


@router.route("/wireguard/interfaces/<uuid>/save",  methods=['POST'])
def save_wireguard_iface(uuid: str):
    if uuid not in router.server.interfaces:
        abort(NOT_FOUND, f"Interface {uuid} not found.")
    data = request.json["data"]
    return RestController(router.server, uuid).save_iface(data)


@router.route("/wireguard/interfaces/<uuid>/apply",  methods=['POST'])
def apply_wireguard_iface(uuid: str):
    data = request.json["data"]
    return RestController(router.server, uuid).apply_iface(data)


@router.route("/wireguard/interfaces/<uuid>/remove",  methods=['DELETE'])
def remove_wireguard_iface(uuid: str):
    if uuid not in router.server.interfaces:
        abort(NOT_FOUND, f"Interface {uuid} not found.")
    return RestController(router.server, uuid).remove_iface()


@router.route("/wireguard/interfaces/<uuid>/regenerate-keys",  methods=['POST'])
def regenerate_iface_keys(uuid: str):
    return RestController(router.server, uuid).regenerate_iface_keys()


@router.route("/wireguard/interfaces/<uuid>",  methods=['POST'])
def operate_wireguard_iface(uuid: str):
    action = request.json["action"].lower()
    if action == "start":
        try:
            router.server.iface_up(uuid)
            return Response(status=NO_CONTENT)
        except WireguardError as e:
            return Response(str(e), status=e.http_code)
    elif action == "restart":
        try:
            router.server.restart_iface(uuid)
            return Response(status=NO_CONTENT)
        except WireguardError as e:
            return Response(str(e), status=e.http_code)
    elif action == "stop":
        try:
            router.server.iface_down(uuid)
            return Response(status=NO_CONTENT)
        except WireguardError as e:
            return Response(str(e), status=e.http_code)
    else:
        abort(BAD_REQUEST, f"Invalid action request: '{action}'")


@router.route("/wireguard/peers/add",  methods=['GET'])
def create_wireguard_peer():
    iface = None
    iface_uuid = request.args.get("interface")
    if iface_uuid:
        if iface_uuid not in router.server.interfaces:
            abort(BAD_REQUEST, f"Unable to create peer for unknown interface '{iface_uuid}'.")
        iface = router.server.interfaces[iface_uuid]
    peer = router.server.generate_peer(iface)
    interfaces = get_wg_interfaces_summary(wg_bin=router.server.config.wg_bin,
                                           interfaces=list(router.server.interfaces.values())).values()
    context = {
        "title": "Add peer",
        "peer": peer,
        "interfaces": interfaces,
        "EMPTY_FIELD": EMPTY_FIELD,
        "APP_NAME": APP_NAME
    }
    return ViewController("web/wireguard-add-peer.html", **context).load()


@router.route("/wireguard/peers/add",  methods=['POST'])
def add_wireguard_peer():
    data = request.json["data"]
    return RestController(router.server).add_peer(data)


@router.route("/wireguard/peers/<uuid>/remove",  methods=['DELETE'])
def remove_wireguard_peer(uuid: str):
    return RestController(router.server).remove_peer(uuid)


@router.route("/themes")
def themes():
    context = {
        "title": "Themes"
    }
    return ViewController("web/themes.html", **context).load()


@router.app_errorhandler(BAD_REQUEST)
def bad_request(err):
    error_code = 400
    context = {
        "title": error_code,
        "error_code": error_code,
        "error_msg": str(err).split(":", 1)[1]
    }
    return ViewController("error/error-main.html", **context).load(), error_code


@router.app_errorhandler(UNAUTHORIZED)
def unauthorized(err):
    error_code = 401
    context = {
        "title": error_code,
        "error_code": error_code,
        "error_msg": str(err).split(":", 1)[1]
    }
    return ViewController("error/error-main.html", **context).load(), error_code


@router.app_errorhandler(NOT_FOUND)
def not_found(err):
    error_code = 404
    context = {
        "title": error_code,
        "error_code": error_code,
        "error_msg": str(err).split(":", 1)[1],
        "image": "/static/assets/img/error-404-monochrome.svg"
    }
    return ViewController("error/error-img.html", **context).load(), error_code


@router.app_errorhandler(INTERNAL_SERVER_ERROR)
def not_found(err):
    error_code = 500
    context = {
        "title": error_code,
        "error_code": error_code,
        "error_msg": str(err).split(":", 1)[1]
    }
    return ViewController("error/error-main.html", **context).load(), error_code
