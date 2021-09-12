import http
import json
from datetime import datetime, timedelta
from http.client import BAD_REQUEST, NOT_FOUND, INTERNAL_SERVER_ERROR, UNAUTHORIZED, NO_CONTENT
from logging import warning, debug, error, info
from typing import List, Dict, Any, Union

from flask import Blueprint, abort, request, Response, redirect, url_for
from flask_login import current_user, login_required, login_user

from core.config.linguard_config import config as linguard_config
from core.config.logger_config import config as logger_config
from core.config.traffic_config import config as traffic_config
from core.config.web_config import config as web_config
from core.config_manager import config_manager
from core.drivers.traffic_storage_driver import TrafficData
from core.exceptions import WireguardError
from core.models import interfaces, Interface, get_all_peers, Peer
from core.traffic_storage import bytes_to_gb
from core.utils import is_wg_iface_up, get_wg_interfaces_summary
from system_utils import get_routing_table, list_to_str, get_system_interfaces, log_exception
from web.controllers.RestController import RestController
from web.controllers.ViewController import ViewController
from web.models import users
from web.static.assets.resources import EMPTY_FIELD, APP_NAME


class Router(Blueprint):

    def __init__(self, name, import_name):
        super().__init__(name, import_name)
        self.login_attempts = 1
        self.banned_until = None


router = Router("router", __name__)


@router.route("/")
@router.route("/dashboard")
@login_required
def index():
    if traffic_config.enabled:
        traffic = traffic_config.driver.get_session_and_stored_data()
    else:
        traffic = {datetime.now(): traffic_config.driver.get_session_data()}
    iface_names = []
    ifaces_traffic = [
        {"label": "Received", "data": []},
        {"label": "Transmitted", "data": []},
    ]
    peer_names = []
    peers_traffic = [
        {"label": "Received", "data": []},
        {"label": "Transmitted", "data": []},
    ]
    for iface in interfaces.values():
        iface_names.append(iface.name)
        iface_traffic = __get_total_traffic__(iface.name, traffic)
        ifaces_traffic[0]["data"].append(bytes_to_gb(iface_traffic.rx))
        ifaces_traffic[1]["data"].append(bytes_to_gb(iface_traffic.tx))
        for peer in iface.peers.values():
            peer_names.append(peer.name)
            peer_traffic = __get_total_traffic__(peer.name, traffic)
            peers_traffic[0]["data"].append(bytes_to_gb(peer_traffic.rx))
            peers_traffic[1]["data"].append(bytes_to_gb(peer_traffic.tx))

    context = {
        "title": "Dashboard",
        "interfaces_chart": {"labels": iface_names, "datasets": ifaces_traffic},
        "peers_chart": {"labels": peer_names, "datasets": peers_traffic},
        "interfaces": interfaces,
        "last_update": datetime.now().strftime("%H:%M"),
        "EMPTY_FIELD": EMPTY_FIELD,
        "traffic_config": traffic_config
    }
    return ViewController("web/index.html", **context).load()


def __get_total_traffic__(name: str, traffic: Dict[datetime, Dict[str, TrafficData]]) -> TrafficData:
    rx = 0
    tx = 0
    for timestamp, data in traffic.items():
        if name in data:
            rx += data[name].rx
            tx += data[name].tx
    return TrafficData(rx, tx)


@router.route("/logout")
@login_required
def logout():
    current_user.logout()
    return redirect(url_for("router.index"))


@router.route("/signup", methods=["GET"])
def signup():
    if len(users) > 0:
        return redirect(url_for("router.index"))
    from web.forms import SignupForm
    context = {
        "title": "Create admin account",
        "form": SignupForm()
    }
    return ViewController("web/signup.html", **context).load()


@router.route("/signup", methods=["POST"])
def signup_post():
    if len(users) > 0:
        abort(http.HTTPStatus.UNAUTHORIZED)
    from web.forms import SignupForm
    form = SignupForm(request.form)
    return RestController().signup(form)


@router.route("/login", methods=["GET"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("router.index"))
    if len(users) < 1:
        return redirect(url_for("router.signup", next=request.args.get("next", None)))
    from web.forms import LoginForm
    context = {
        "title": "Login",
        "form": LoginForm()
    }
    now = datetime.now()
    if router.banned_until and now < router.banned_until:
        context["banned_for"] = (router.banned_until - now).seconds
    else:
        router.banned_until = None
        router.login_attempts = 1
    return ViewController("web/login.html", **context).load()


@router.route("/login", methods=["POST"])
def login_post():
    from web.forms import LoginForm
    form = LoginForm(request.form)
    info(f"Logging in user '{form.username.data}'...")
    max_attempts = int(web_config.login_attempts)
    if max_attempts and router.login_attempts > max_attempts:
        router.banned_until = datetime.now() + timedelta(minutes=2)
        return redirect(form.next.data or url_for("router.index"))
    router.login_attempts += 1
    if not form.validate():
        error("Unable to validate form.")
        context = {
            "title": "Login",
            "form": form
        }
        return ViewController("web/login.html", **context).load()
    u = users.get_value_by_attr("name", form.username.data)
    if not login_user(u, form.remember_me.data):
        error(f"Unable to log user in.")
        abort(http.HTTPStatus.INTERNAL_SERVER_ERROR)
    info(f"Successfully logged user '{u.name}' in!")
    router.web_login_attempts = 1
    return redirect(form.next.data or url_for("router.index"))


@router.route("/network")
@login_required
def network():
    wg_ifaces = list(interfaces.values())
    ifaces = get_network_ifaces(wg_ifaces)
    routes = get_routing_table()
    context = {
        "title": "Network",
        "interfaces": ifaces,
        "routes": routes,
        "last_update": datetime.now().strftime("%H:%M"),
        "EMPTY_FIELD": EMPTY_FIELD
    }
    return ViewController("web/network.html", **context).load()


def get_network_ifaces(wg_interfaces: List[Interface]) -> Dict[str, Dict[str, Any]]:
    interfaces = get_system_interfaces_summary()
    for iface in wg_interfaces:
        if iface.name not in interfaces:
            interfaces[iface.name] = {
                "uuid": iface.uuid,
                "name": iface.name,
                "status": "down",
                "ipv4": iface.ipv4_address,
                "ipv6": EMPTY_FIELD,
                "mac": EMPTY_FIELD,
                "flags": EMPTY_FIELD
            }
        else:
            if iface in wg_interfaces:
                interfaces[iface.name]["uuid"] = iface.uuid
            if interfaces[iface.name]["status"] == "unknown":
                if is_wg_iface_up(iface.name):
                    interfaces[iface.name]["status"] = "up"
                else:
                    interfaces[iface.name]["status"] = "down"
        interfaces[iface.name]["editable"] = True

    return interfaces


def get_system_interfaces_summary() -> Dict[str, Dict[str, Any]]:
    interfaces = {}
    for item in get_system_interfaces().values():
        flag_list = list(filter(lambda flag: "UP" not in flag, item["flags"]))
        flags = list_to_str(flag_list)
        iface = {
            "name": item["ifname"],
            "flags": flags,
            "status": item["operstate"].lower()
        }
        if "LOOPBACK" in iface["flags"]:
            iface["status"] = "up"
        if "address" in item:
            iface["mac"] = item["address"]
        else:
            iface["mac"] = EMPTY_FIELD
        addr_info = item["addr_info"]
        if addr_info:
            ipv4_info = addr_info[0]
            iface["ipv4"] = f"{ipv4_info['local']}/{ipv4_info['prefixlen']}"
            if len(addr_info) > 1:
                ipv6_info = addr_info[1]
                iface["ipv6"] = f"{ipv6_info['local']}/{ipv6_info['prefixlen']}"
            else:
                iface["ipv6"] = EMPTY_FIELD
        else:
            iface["ipv4"] = EMPTY_FIELD
            iface["ipv6"] = EMPTY_FIELD
        interfaces[iface["name"]] = iface
    return interfaces


@router.route("/wireguard")
@login_required
def wireguard():
    wg_ifaces = list(interfaces.values())
    ifaces = get_wg_interfaces_summary(wg_bin=linguard_config.wg_bin, interfaces=wg_ifaces)
    context = {
        "title": "Wireguard",
        "interfaces": ifaces,
        "last_update": datetime.now().strftime("%H:%M"),
        "EMPTY_FIELD": EMPTY_FIELD
    }
    return ViewController("web/wireguard.html", **context).load()


@router.route("/wireguard/interfaces/add", methods=['GET'])
@login_required
def create_wireguard_iface():
    from web.forms import AddInterfaceForm
    form = AddInterfaceForm.populate(AddInterfaceForm())
    context = {
        "title": "Add interface",
        "form": form,
        "app_name": APP_NAME
    }
    return ViewController("web/wireguard-add-iface.html", **context).load()


@router.route("/wireguard/interfaces/add", methods=['POST'])
@login_required
def add_wireguard_iface():
    from web.forms import AddInterfaceForm
    form = AddInterfaceForm.from_form(AddInterfaceForm(request.form))
    view = "web/wireguard-add-iface.html"
    context = {
        "title": "Add interface",
        "form": form,
        "app_name": APP_NAME
    }
    if not form.validate():
        error("Unable to validate form")
        return ViewController(view, **context).load()
    try:
        RestController().add_iface(form)
        return redirect(url_for("router.wireguard"))
    except Exception as e:
        log_exception(e)
        context["error"] = True
        context["error_details"] = e
    return ViewController(view, **context).load()


def load_traffic_data(item: Union[Peer, Interface]):
    labels = []
    datasets = {"rx": [], "tx": []}
    for timestamp, traffic_data in traffic_config.driver.load_data().items():
        labels.append(str(timestamp))
        for device, data in traffic_data.items():
            if device == item.name:
                datasets["rx"].append(bytes_to_gb(data.rx))
                datasets["tx"].append(bytes_to_gb(data.tx))
                break
    return {"labels": labels, "datasets": datasets}


@router.route("/wireguard/interfaces/<uuid>", methods=['GET', "POST"])
@login_required
def get_wireguard_iface(uuid: str):
    if uuid not in interfaces:
        abort(NOT_FOUND, f"Unknown interface '{uuid}'.")
    iface = interfaces[uuid]
    view = "web/wireguard-iface.html"
    data = load_traffic_data(iface)
    session_data = traffic_config.driver.get_session_data()
    iface_traffic = session_data.get(iface.name, TrafficData(0, 0))
    context = {
        "title": "Interface",
        "iface": iface,
        "iface_status": iface.status,
        "last_update": datetime.now().strftime("%H:%M"),
        "EMPTY_FIELD": EMPTY_FIELD,
        "app_name": APP_NAME,
        "chart": {"labels": data["labels"], "datasets": data["datasets"]},
        "iface_traffic": TrafficData(bytes_to_gb(iface_traffic.rx), bytes_to_gb(iface_traffic.tx)),
        "session_traffic": session_data,
        "traffic_config": traffic_config
    }
    from web.forms import EditInterfaceForm
    if request.method == 'GET':
        form = EditInterfaceForm.from_interface(iface)
        context["form"] = form
        return ViewController("web/wireguard-iface.html", **context).load()
    form = EditInterfaceForm.from_form(EditInterfaceForm(request.form), iface)
    context["form"] = form
    if not form.validate():
        error("Unable to validate form.")
        return ViewController(view, **context).load()
    try:
        RestController().apply_iface(iface, form)
        context["iface_status"] = iface.status
        context["success"] = True
        context["success_details"] = "Interface updated successfully."
    except Exception as e:
        log_exception(e)
        context["error"] = True
        context["error_details"] = e
    return ViewController(view, **context).load()


@router.route("/wireguard/interfaces/<uuid>", methods=['DELETE'])
@login_required
def remove_wireguard_iface(uuid: str):
    if uuid not in interfaces:
        abort(NOT_FOUND, f"Interface {uuid} not found.")
    return RestController(uuid).remove_iface()


@router.route("/wireguard/interfaces/<uuid>/<action>", methods=['POST'])
@login_required
def operate_wireguard_iface(uuid: str, action: str):
    action = action.lower()
    try:
        if action == "start":
            interfaces[uuid].up()
            return Response(status=NO_CONTENT)
        if action == "restart":
            interfaces[uuid].restart()
            return Response(status=NO_CONTENT)
        if action == "stop":
            interfaces[uuid].down()
            return Response(status=NO_CONTENT)
        raise WireguardError(f"Invalid operation: {action}", BAD_REQUEST)
    except WireguardError as e:
        return Response(e.cause, status=e.http_code)


@router.route("/wireguard/<action>", methods=['POST'])
@login_required
def operate_wireguard_ifaces(action: str):
    action = action.lower()
    try:
        if action == "start":
            for iface in interfaces.values():
                iface.up()
            return Response(status=NO_CONTENT)
        if action == "restart":
            for iface in interfaces.values():
                iface.restart()
            return Response(status=NO_CONTENT)
        if action == "stop":
            for iface in interfaces.values():
                iface.down()
            return Response(status=NO_CONTENT)
        raise WireguardError(f"invalid operation: {action}", BAD_REQUEST)
    except WireguardError as e:
        return Response(e.cause, status=e.http_code)


@router.route("/wireguard/interfaces/<uuid>/download", methods=['GET'])
@login_required
def download_wireguard_iface(uuid: str):
    if uuid not in interfaces.keys():
        error(f"Unknown interface {uuid}")
        abort(NOT_FOUND)
    return RestController().download_iface(interfaces[uuid])


@router.route("/wireguard/peers/add", methods=['GET'])
@login_required
def create_wireguard_peer():
    iface_uuid = request.args.get("interface", None)
    iface = interfaces.get(iface_uuid, None)
    from web.forms import AddPeerForm
    form = AddPeerForm.populate(AddPeerForm(), iface)
    context = {
        "title": "Add peer",
        "form": form,
        "app_name": APP_NAME
    }
    return ViewController("web/wireguard-add-peer.html", **context).load()


@router.route("/wireguard/peers/add", methods=['POST'])
@login_required
def add_wireguard_peer():
    from web.forms import AddPeerForm
    form = AddPeerForm.from_form(AddPeerForm(request.form))
    view = "web/wireguard-add-peer.html"
    context = {
        "title": "Add Peer",
        "form": form,
        "app_name": APP_NAME
    }
    if not form.validate():
        error("Unable to validate form")
        return ViewController(view, **context).load()
    try:
        peer = RestController().add_peer(form)
        return redirect(f"{request.url_root}wireguard/peers/{peer.uuid}")
    except Exception as e:
        log_exception(e)
        context["error"] = True
        context["error_details"] = e
    return ViewController(view, **context).load()


@router.route("/wireguard/peers/<uuid>", methods=['DELETE'])
@login_required
def remove_wireguard_peer(uuid: str):
    peer = get_all_peers().get(uuid, None)
    if not peer:
        raise WireguardError(f"Unknown peer '{uuid}'.", NOT_FOUND)
    return RestController().remove_peer(peer)


@router.route("/wireguard/peers/<uuid>", methods=['GET', "POST"])
@login_required
def get_wireguard_peer(uuid: str):
    peer = get_all_peers().get(uuid, None)
    if not peer:
        raise WireguardError(f"Unknown peer '{uuid}'.", NOT_FOUND)
    view = "web/wireguard-peer.html"
    data = load_traffic_data(peer)
    session_data = traffic_config.driver.get_session_data().get(peer.name, TrafficData(0, 0))
    context = {
        "title": "Peer",
        "peer": peer,
        "last_update": datetime.now().strftime("%H:%M"),
        "EMPTY_FIELD": EMPTY_FIELD,
        "APP_NAME": APP_NAME,
        "chart": {"labels": data["labels"], "datasets": data["datasets"]},
        "session_traffic": TrafficData(bytes_to_gb(session_data.rx), bytes_to_gb(session_data.tx),
                                       session_data.last_handshake),
        "traffic_config": traffic_config
    }
    from web.forms import EditPeerForm
    if request.method == 'GET':
        form = EditPeerForm.from_peer(peer)
        context["form"] = form
        return ViewController(view, **context).load()
    form = EditPeerForm.from_form(EditPeerForm(request.form), peer)
    context["form"] = form
    if not form.validate():
        error("Unable to validate form.")
        return ViewController(view, **context).load()
    try:
        RestController().save_peer(peer, form)
        context["success"] = True
        context["success_details"] = "Peer updated successfully."
    except Exception as e:
        log_exception(e)
        context["error"] = True
        context["error_details"] = e
    return ViewController(view, **context).load()


@router.route("/wireguard/peers/<uuid>/download", methods=['GET'])
@login_required
def download_wireguard_peer(uuid: str):
    peer = get_all_peers().get(uuid, None)
    if not peer:
        msg = f"Unknown peer '{uuid}'."
        error(msg)
        abort(NOT_FOUND, msg)
    return RestController().download_peer(peer)


@router.route("/themes")
@login_required
def themes():
    context = {
        "title": "Themes"
    }
    return ViewController("web/themes.html", **context).load()


@router.route("/settings")
@login_required
def settings():
    from web.forms import SettingsForm
    form = SettingsForm()
    form.traffic_enabled.data = traffic_config.enabled
    form.log_overwrite.data = logger_config.overwrite
    form.traffic_driver_options.data = json.dumps(traffic_config.driver.__to_yaml_dict__(), indent=4, sort_keys=True)
    context = {
        "title": "Settings",
        "form": form,
        "app_name": APP_NAME
    }
    return ViewController("web/settings.html", **context).load()


@router.route("/settings", methods=['POST'])
@login_required
def save_settings():
    from web.forms import SettingsForm
    form = SettingsForm(request.form)
    view = "web/settings.html"
    context = {
        "title": "Settings",
        "form": form
    }
    if not form.validate():
        error("Unable to validate form")
        return ViewController(view, **context).load()
    try:
        RestController().save_settings(form)
        # Fill fields with default values if they were left unfilled
        form.log_file.data = form.log_file.data or logger_config.logfile

        form.web_secret_key.data = form.web_secret_key.data or web_config.secret_key
        form.web_credentials_file.data = form.web_credentials_file.data or web_config.credentials_file

        form.app_endpoint.data = form.app_endpoint.data or linguard_config.endpoint
        form.app_wg_bin.data = form.app_wg_bin.data or linguard_config.wg_bin
        form.app_wg_quick_bin.data = form.app_wg_quick_bin.data or linguard_config.wg_quick_bin
        form.app_iptables_bin.data = form.app_iptables_bin.data or linguard_config.iptables_bin
        form.app_interfaces_folder.data = form.app_interfaces_folder.data or linguard_config.interfaces_folder

        context["success"] = True
        context["success_details"] = "Settings updated!"
        context["warning"] = True
        context["warning_details"] = f"You may need to restart {APP_NAME} to apply some changes."
    except Exception as e:
        log_exception(e)
        context["error"] = True
        context["error_details"] = e
    return ViewController(view, **context).load()


@router.route("/profile", methods=['GET'])
@login_required
def profile():
    from web.forms import ProfileForm, PasswordResetForm
    profile_form = ProfileForm()
    profile_form.username.data = current_user.name
    if request.form:
        password_reset_form = PasswordResetForm(request.form)
    else:
        password_reset_form = PasswordResetForm()
    view = "web/profile.html"
    context = {
        "title": "Profile",
        "profile_form": profile_form,
        "password_reset_form": password_reset_form,
        "app_name": APP_NAME
    }
    return ViewController(view, **context).load()


@router.route("/profile", methods=['POST'])
@login_required
def save_profile():
    if "new_password" in request.form:
        return password_reset()
    from web.forms import ProfileForm, PasswordResetForm
    view = "web/profile.html"
    profile_form = ProfileForm(request.form)
    password_reset_form = PasswordResetForm()
    context = {
        "title": "Profile",
        "profile_form": profile_form,
        "password_reset_form": password_reset_form,
        "app_name": APP_NAME
    }
    if not profile_form.validate():
        error("Unable to validate form")
        return ViewController(view, **context).load()
    try:
        current_user.name = profile_form.username.data
        config_manager.save_credentials()
        context["success"] = True
        context["success_details"] = "Profile updated!"
    except Exception as e:
        context["error"] = True
        context["error_details"] = e
    return ViewController(view, **context).load()


def password_reset():
    view = "web/profile.html"
    from web.forms import PasswordResetForm, ProfileForm
    profile_form = ProfileForm()
    profile_form.username.data = current_user.name
    password_reset_form = PasswordResetForm(request.form)
    context = {
        "title": "Profile",
        "profile_form": profile_form,
        "password_reset_form": password_reset_form,
        "app_name": APP_NAME
    }
    if not password_reset_form.validate():
        error("Unable to validate form")
        return ViewController(view, **context).load()
    try:
        current_user.password = password_reset_form.new_password.data
        config_manager.save_credentials()
        context["success"] = True
        context["success_details"] = "Password updated!"
    except Exception as e:
        context["error"] = True
        context["error_details"] = e
    return ViewController(view, **context).load()


@router.app_errorhandler(BAD_REQUEST)
def bad_request(err):
    error_code = int(BAD_REQUEST)
    context = {
        "title": error_code,
        "error_code": error_code,
        "error_msg": str(err).split(":", 1)[1]
    }
    return ViewController("error/error-main.html", **context).load(), error_code


@router.app_errorhandler(UNAUTHORIZED)
def unauthorized(err):
    warning(f"Unauthorized request from {request.remote_addr}!")
    if request.method == "GET":
        debug(f"Redirecting to login...")
        try:
            next = url_for(request.endpoint)
        except Exception:
            uuid = request.path.rsplit("/", 1)[-1]
            next = url_for(request.endpoint, uuid=uuid)
        return redirect(url_for("router.login", next=next))
    error_code = int(UNAUTHORIZED)
    context = {
        "title": error_code,
        "error_code": error_code,
        "error_msg": str(err).split(":", 1)[1]
    }
    return ViewController("error/error-main.html", **context).load(), error_code


@router.app_errorhandler(NOT_FOUND)
def not_found(err):
    error_code = int(NOT_FOUND)
    context = {
        "title": error_code,
        "error_code": error_code,
        "error_msg": str(err).split(":", 1)[1],
        "image": "/static/assets/img/error-404-monochrome.svg"
    }
    return ViewController("error/error-img.html", **context).load(), error_code


@router.app_errorhandler(INTERNAL_SERVER_ERROR)
def not_found(err):
    error_code = int(INTERNAL_SERVER_ERROR)
    context = {
        "title": error_code,
        "error_code": error_code,
        "error_msg": str(err).split(":", 1)[1]
    }
    return ViewController("error/error-main.html", **context).load(), error_code
