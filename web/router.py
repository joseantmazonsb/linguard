from datetime import datetime

from flask import Blueprint, abort, request, Response

from core.wireguard.exceptions import WireguardError
from web.controllers.RestController import RestController
from web.controllers.ViewController import ViewController
from web.utils import get_all_interfaces, get_routing_table, get_wg_interfaces_summary, get_wg_interface_status
from core.wireguard.server import Server
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
    interfaces = get_all_interfaces(wg_bin=router.server.wg_bin, wg_interfaces=wg_ifaces)
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
    interfaces = get_wg_interfaces_summary(wg_bin=router.server.wg_bin, interfaces=wg_ifaces)
    context = {
        "title": "Wireguard",
        "interfaces": interfaces,
        "last_update": datetime.now().strftime("%H:%M"),
        "EMPTY_FIELD": EMPTY_FIELD
    }
    return ViewController("web/wireguard.html", **context).load()


@router.route("/wireguard/interfaces/add",  methods=['GET'])
def create_wireguard_iface():
    name = None
    iface_param = request.args.get("iface")
    if iface_param:
        name = iface_param
    iface = router.server.create_interface(name)
    context = {
        "title": "Add interface",
        "iface": iface,
        "EMPTY_FIELD": EMPTY_FIELD,
        "APP_NAME": APP_NAME
    }
    return ViewController("web/wireguard-add-iface.html", **context).load()


@router.route("/wireguard/interfaces/add",  methods=['POST'])
def add_wireguard_iface():
    data = request.json["data"]
    return RestController(router.server, data["name"]).add_iface(data)


@router.route("/wireguard/interfaces/<uuid>",  methods=['GET'])
def get_wireguard_iface(uuid: str):
    iface = router.server.interfaces[uuid]
    iface_status = get_wg_interface_status(router.server.wg_bin, iface.name)
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
        return Response(f"Interface {uuid} not found.", status=404)
    data = request.json["data"]
    return RestController(router.server, uuid).save_iface(data)


@router.route("/wireguard/interfaces/<uuid>/apply",  methods=['POST'])
def apply_wireguard_iface(uuid: str):
    data = request.json["data"]
    return RestController(router.server, uuid).apply_iface(data)


@router.route("/wireguard/interfaces/<uuid>/remove",  methods=['POST'])
def remove_wireguard_iface(uuid: str):
    if uuid not in router.server.interfaces:
        return Response(f"Interface {uuid} not found.", status=404)
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
            return Response(status=204)
        except WireguardError as e:
            return Response(str(e), status=e.http_code)
    elif action == "restart":
        try:
            router.server.restart_iface(uuid)
            return Response(status=204)
        except WireguardError as e:
            return Response(str(e), status=e.http_code)
    elif action == "stop":
        try:
            router.server.iface_down(uuid)
            return Response(status=204)
        except WireguardError as e:
            return Response(str(e), status=e.http_code)
    else:
        return Response(f"Invalid action request: '{action}'", status=400)


@router.route("/themes")
def themes():
    context = {
        "title": "Themes"
    }
    return ViewController("web/themes.html", **context).load()


@router.app_errorhandler(400)
def bad_request(err):
    error_code = 400
    context = {
        "title": error_code,
        "error_code": error_code,
        "error_msg": str(err).split(":", 1)[1]
    }
    return ViewController("error/error-main.html", **context).load(), error_code


@router.app_errorhandler(401)
def not_found(err):
    error_code = 401
    context = {
        "title": error_code,
        "error_code": error_code,
        "error_msg": str(err).split(":", 1)[1]
    }
    return ViewController("error/error-main.html", **context).load(), error_code


@router.app_errorhandler(404)
def not_found(err):
    error_code = 404
    context = {
        "title": error_code,
        "error_code": error_code,
        "error_msg": str(err).split(":", 1)[1],
        "image": "/static/assets/img/error-404-monochrome.svg"
    }
    return ViewController("error/error-img.html", **context).load(), error_code


@router.app_errorhandler(500)
def not_found(err):
    error_code = 500
    context = {
        "title": error_code,
        "error_code": error_code,
        "error_msg": str(err).split(":", 1)[1]
    }
    return ViewController("error/error-main.html", **context).load(), error_code
