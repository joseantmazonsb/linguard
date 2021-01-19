from datetime import datetime
from logging import debug

from flask import Blueprint, abort, request

from web.utils import get_all_interfaces, get_routing_table, get_wg_interfaces_summary
from core.wireguard.server import Server
from web.controller import Controller
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
    return Controller("web/index.html", **context).load()


@router.route("/login")
def login():
    context = {
        "title": "Login"
    }
    return Controller("web/login.html", **context).load()


@router.route("/signup")
def signup():
    context = {
        "title": "Sign up"
    }
    return Controller("web/signup.html", **context).load()


@router.route("/network")
def network():
    interfaces = get_all_interfaces(wg_bin=router.server.wg_bin, wg_interfaces=router.server.interfaces.values())
    routes = get_routing_table()
    context = {
        "title": "Network",
        "interfaces": interfaces,
        "routes": routes,
        "last_update": datetime.now().strftime("%H:%M"),
        "EMPTY_FIELD": EMPTY_FIELD
    }
    return Controller("web/network.html", **context).load()


@router.route("/wireguard")
def wireguard():
    interfaces = get_wg_interfaces_summary(wg_bin=router.server.wg_bin, interfaces=router.server.interfaces.values())
    context = {
        "title": "Wireguard",
        "interfaces": interfaces,
        "last_update": datetime.now().strftime("%H:%M"),
        "EMPTY_FIELD": EMPTY_FIELD
    }
    return Controller("web/wireguard.html", **context).load()


@router.route("/wireguard/interfaces/<name>",  methods=['POST'])
def wireguard_iface(name: str):
    action = request.json["action"].lower()
    debug(f"User requested to {action} {name}.")
    if action == "start":
        router.server.iface_up(name)
        return "200"
    elif action == "restart":
        router.server.restart_iface(name)
        return "200"
    elif action == "stop":
        router.server.iface_down(name)
        return "200"
    else:
        abort(500)


@router.route("/themes")
def themes():
    context = {
        "title": "Themes"
    }
    return Controller("web/themes.html", **context).load()


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
    return Controller("error/error-main.html", **context).load(), error_code


@router.app_errorhandler(401)
def not_found(err):
    error_code = 401
    context = {
        "title": error_code,
        "error_code": error_code,
        "error_msg": str(err).split(":", 1)[1]
    }
    return Controller("error/error-main.html", **context).load(), error_code


@router.app_errorhandler(404)
def not_found(err):
    error_code = 404
    context = {
        "title": error_code,
        "error_code": error_code,
        "error_msg": str(err).split(":", 1)[1],
        "image": "/static/assets/img/error-404-monochrome.svg"
    }
    return Controller("error/error-img.html", **context).load(), error_code


@router.app_errorhandler(500)
def not_found(err):
    error_code = 500
    context = {
        "title": error_code,
        "error_code": error_code,
        "error_msg": str(err).split(":", 1)[1]
    }
    return Controller("error/error-main.html", **context).load(), error_code
