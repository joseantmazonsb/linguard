from datetime import datetime

from flask import Blueprint, abort, request, Response

from core.wireguard.exceptions import WireguardError
from web.controllers.ViewController import ViewController
from web.controllers.WireguardSaveIfaceController import WireguardSaveIfaceController
from web.utils import get_all_interfaces, get_routing_table, get_wg_interfaces_summary
from core.wireguard.server import Server
from web.static.assets.resources import EMPTY_FIELD


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


@router.route("/wireguard/interfaces/<name>",  methods=['GET'])
def get_wireguard_iface(name: str):
    iface = router.server.interfaces[name]
    context = {
        "title": "Edit interface",
        "iface": iface,
        "len": len,
        "last_update": datetime.now().strftime("%H:%M"),
        "EMPTY_FIELD": EMPTY_FIELD
    }
    return ViewController("web/wireguard-iface.html", **context).load()


@router.route("/wireguard/interfaces/<name>/save",  methods=['POST'])
def save_wireguard_iface(name: str):
    try:
        data = request.json["data"]
        return WireguardSaveIfaceController(router.server, data, name).serve()
    except WireguardError as e:
        return Response(str(e), status=400)
    except Exception as e:
        return Response(str(e), status=500)


@router.route("/wireguard/interfaces/<name>",  methods=['POST'])
def operate_wireguard_iface(name: str):
    action = request.json["action"].lower()
    if action == "start":
        try:
            router.server.iface_up(name)
            return Response(status=204)
        except WireguardError as e:
            return Response(str(e), status=500)
    elif action == "restart":
        try:
            router.server.restart_iface(name)
            return Response(status=204)
        except WireguardError as e:
            return Response(str(e), status=500)
    elif action == "stop":
        try:
            router.server.iface_down(name)
            return Response(status=204)
        except WireguardError as e:
            return Response(str(e), status=500)
    else:
        return Response(f"Invalid action request: '{action}'", status=400)


@router.route("/themes")
def themes():
    context = {
        "title": "Themes"
    }
    return ViewController("web/themes.html", **context).load()


@router.route("/error")
def error_test():
    abort(400)


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
