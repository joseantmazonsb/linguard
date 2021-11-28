import json
from datetime import datetime
from functools import wraps
from http.client import BAD_REQUEST, NOT_FOUND, INTERNAL_SERVER_ERROR, UNAUTHORIZED, NO_CONTENT
from io import StringIO
from ipaddress import IPv4Address
from logging import warning, debug, error, info
from typing import List, Dict, Any, Union
from urllib.parse import parse_qs, urlparse

from flask import Blueprint, abort, request, Response, redirect, url_for
from flask_login import current_user, login_required, login_user

from linguard.common.models.user import users
from linguard.common.properties import global_properties
from linguard.common.utils.logs import log_exception
from linguard.common.utils.network import get_routing_table, get_system_interfaces
from linguard.common.utils.strings import list_to_str
from linguard.common.utils.time import get_time_ago
from linguard.core.config.logger import config as logger_config
from linguard.core.config.traffic import config as traffic_config
from linguard.core.config.web import config as web_config
from linguard.core.config.wireguard import config as wireguard_config
from linguard.core.drivers.traffic_storage_driver import TrafficData
from linguard.core.exceptions import WireguardError
from linguard.core.managers.config import config_manager
from linguard.core.models import interfaces, Interface, get_all_peers, Peer
from linguard.core.utils.wireguard import is_wg_iface_up
from linguard.web.client import clients, Client
from linguard.web.controllers.RestController import RestController
from linguard.web.controllers.ViewController import ViewController
from linguard.web.static.assets.resources import EMPTY_FIELD, APP_NAME


def get_referrer_next_value():
    next_url = parse_qs(urlparse(request.referrer).query).get("next", None)
    if not next_url or len(next_url) < 1:
        return None
    return next_url[0]


class Router(Blueprint):

    def __init__(self, name, import_name):
        super().__init__(name, import_name)


router = Router("router", __name__)

config_manager.load()


def setup_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if global_properties.setup_required and not global_properties.setup_file_exists():
            return redirect(url_for("router.setup", next=request.args.get("next", get_referrer_next_value())))
        return f(*args, **kwargs)

    return wrapped


@router.route("/")
@router.route("/dashboard")
@login_required
@setup_required
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
        iface_traffic = __get_total_traffic__(iface.uuid, traffic)
        ifaces_traffic[0]["data"].append(iface_traffic.rx)
        ifaces_traffic[1]["data"].append(iface_traffic.tx)
        for peer in iface.peers.values():
            peer_names.append(peer.name)
            peer_traffic = __get_total_traffic__(peer.uuid, traffic)
            peers_traffic[0]["data"].append(peer_traffic.rx)
            peers_traffic[1]["data"].append(peer_traffic.tx)

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


def __get_total_traffic__(uuid: str, traffic: Dict[datetime, Dict[str, TrafficData]]) -> TrafficData:
    rx = 0
    tx = 0
    for data in reversed(list(traffic.values())):
        # Get only last appearance
        if uuid in data:
            rx += data[uuid].rx
            tx += data[uuid].tx
            break
    return TrafficData(rx, tx)


@router.route("/logout")
@login_required
@setup_required
def logout():
    current_user.logout()
    return redirect(url_for("router.index"))


@router.route("/signup", methods=["GET"])
def signup():
    if len(users) > 0:
        return redirect(url_for("router.index"))
    from linguard.web.forms import SignupForm
    context = {
        "title": "Create admin account",
        "form": SignupForm()
    }
    return ViewController("web/signup.html", **context).load()


@router.route("/signup", methods=["POST"])
def signup_post():
    if len(users) > 0:
        abort(UNAUTHORIZED)
    from linguard.web.forms import SignupForm
    form = SignupForm(request.form)
    return RestController().signup(form)


@router.route("/login", methods=["GET"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("router.index"))
    if len(users) < 1:
        return redirect(url_for("router.signup", next=request.args.get("next", None)))
    from linguard.web.forms import LoginForm
    context = {
        "title": "Login",
        "form": LoginForm()
    }
    client = get_client()
    if client.is_banned():
        context["banned_for"] = (client.banned_until - datetime.now()).seconds
    return ViewController("web/login.html", **context).load()


def get_client() -> Client:
    client_ip = IPv4Address(request.remote_addr)
    if client_ip not in clients:
        clients[client_ip] = Client(client_ip)
    return clients[client_ip]


@router.route("/login", methods=["POST"])
def login_post():
    from linguard.web.forms import LoginForm
    form = LoginForm(request.form)
    info(f"Logging in user '{form.username.data}'...")
    client = get_client()
    if client.is_banned():
        return redirect(form.next.data or url_for("router.index"))
    if not form.validate():
        error("Unable to validate form.")
        context = {
            "title": "Login",
            "form": form
        }
        client.login_attempts += 1
        if web_config.login_attempts and client.login_attempts > int(web_config.login_attempts):
            client.ban()
            context["banned_for"] = (client.banned_until - datetime.now()).seconds
        return ViewController("web/login.html", **context).load()
    del clients[client.ip]
    u = users.get_value_by_attr("name", form.username.data)
    if not login_user(u, form.remember_me.data):
        error(f"Unable to log user in.")
        abort(INTERNAL_SERVER_ERROR)
    info(f"Successfully logged user '{u.name}' in!")
    router.web_login_attempts = 1
    return redirect(request.args.get("next", url_for("router.index")))


@router.route("/network")
@login_required
@setup_required
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
@setup_required
def wireguard():
    context = {
        "title": "Wireguard",
        "interfaces": interfaces,
        "last_update": datetime.now().strftime("%H:%M"),
        "EMPTY_FIELD": EMPTY_FIELD
    }
    return ViewController("web/wireguard.html", **context).load()


@router.route("/wireguard/interfaces/import", methods=['GET'])
@login_required
@setup_required
def import_wireguard_iface():
    context = {
        "title": "Import interfaces",
        "EMPTY_FIELD": EMPTY_FIELD
    }
    return ViewController("web/import.html", **context).load()


@router.route("/wireguard/peers/import", methods=['GET'])
@login_required
@setup_required
def import_wireguard_peer():
    if len(interfaces) < 1:
        abort(BAD_REQUEST, "There are no wireguard interfaces!")
    iface_uuid = request.args.get("interface", None)
    if not iface_uuid:
        abort(BAD_REQUEST, f"No interface provided.")
    iface = interfaces.get(iface_uuid, None)
    if not iface:
        abort(BAD_REQUEST, f"Unknown interface '{iface_uuid}'.")
    context = {
        "title": f"Import peers for {iface.name}",
        "EMPTY_FIELD": EMPTY_FIELD
    }
    return ViewController("web/import.html", **context).load()


@router.route("/wireguard/interfaces/import", methods=['POST'])
@login_required
@setup_required
def add_imported_wireguard_iface():
    context = {
        "title": "Import interfaces",
        "EMPTY_FIELD": EMPTY_FIELD,
        "errors": [],
        "successes": [],
    }
    files = request.files.getlist("files")
    if len(files) < 1 or len(files) == 1 and not files[0].filename:
        context["errors"].append("You must specify one or more files to import!")
        return ViewController("web/import.html", **context).load()
    for file in files:
        try:
            stream = StringIO(file.stream.read().decode("utf-8"))
            iface = Interface.from_wireguard_conf(file.filename.rsplit(".", 1)[0], stream)
            if Interface.is_port_in_use(iface.listen_port):
                raise WireguardError(f"Port <code>{iface.listen_port}</code> is already in use!", BAD_REQUEST)
            if Interface.is_ip_in_use(iface.ipv4_address):
                raise WireguardError(f"Address <code>{iface.ipv4_address}</code> is already in use!", BAD_REQUEST)
            if Interface.is_network_in_use(iface.ipv4_address):
                raise WireguardError(f"Network <code>{iface.ipv4_address.network}</code> is already in use!",
                                     BAD_REQUEST)
            if Interface.is_name_in_use(iface.name):
                raise WireguardError(f"Interface name <code>{iface.name}</code> is already in use", BAD_REQUEST)
            if not Interface.is_name_valid(iface.name):
                msg = f"<code>{iface.name}</code> is not a valid interface name. " \
                      f"It can only contain alphanumeric characters, underscores (_) and " \
                      f"hyphens (-). It must also begin with a letter and be between {Interface.MIN_NAME_LENGTH} and " \
                      f"{Interface.MAX_NAME_LENGTH} characters long."
                raise WireguardError(msg, BAD_REQUEST)
            interfaces[iface.uuid] = iface
            context["successes"].append(f"Interface <code>{iface.name}</code> was successfully imported!")
        except Exception as e:
            log_exception(e)
            context["errors"].append(f"Unable to import file <code>{file.filename}</code>. {str(e)}")
    interfaces.sort()
    config_manager.save()
    return ViewController("web/import.html", **context).load()


@router.route("/wireguard/peers/import", methods=['POST'])
@login_required
@setup_required
def add_imported_wireguard_peer():
    if len(interfaces) < 1:
        abort(BAD_REQUEST, "There are no wireguard interfaces!")
    iface_uuid = request.args.get("interface", None)
    if not iface_uuid:
        abort(BAD_REQUEST, f"No interface provided.")
    iface = interfaces.get(iface_uuid, None)
    if not iface:
        abort(BAD_REQUEST, f"Unknown interface '{iface_uuid}'.")
    context = {
        "title": "Import peers",
        "EMPTY_FIELD": EMPTY_FIELD,
        "errors": [],
        "successes": [],
    }
    files = request.files.getlist("files")
    if len(files) < 1 or len(files) == 1 and not files[0].filename:
        context["errors"].append("You must specify one or more files to import!")
        return ViewController("web/import.html", **context).load()
    for file in files:
        try:
            stream = StringIO(file.stream.read().decode("utf-8"))
            peer = Peer.from_wireguard_conf(file.filename.rsplit(".", 1)[0], stream, iface)
            if not Peer.is_name_valid(peer.name):
                msg = (f"Name <code>{peer.name}</code> is not valid! It "
                       f"can only contain alphanumeric characters, underscores (_), hyphens (-) and whitespaces. "
                       f"It must also begin with a letter and be between {Peer.MIN_NAME_LENGTH} and "
                       f"{Peer.MAX_NAME_LENGTH} characters long.")
                raise WireguardError(msg, BAD_REQUEST)
            if Peer.is_ip_in_use(peer.ipv4_address):
                raise WireguardError(f"Address <code>{peer.ipv4_address}</code> is already in use!", BAD_REQUEST)
            iface.add_peer(peer)
            context["successes"].append(f"Peer <code>{peer.name}</code> was successfully imported!")
        except Exception as e:
            log_exception(e)
            context["errors"].append(f"Unable to import file <code>{file.filename}</code>. {str(e)}")
    config_manager.save()
    return ViewController("web/import.html", **context).load()


@router.route("/wireguard/interfaces/add", methods=['GET'])
@login_required
@setup_required
def create_wireguard_iface():
    from linguard.web.forms import AddInterfaceForm
    form = AddInterfaceForm.populate(AddInterfaceForm())
    context = {
        "title": "Add interface",
        "form": form,

    }
    return ViewController("web/wireguard-add-iface.html", **context).load()


@router.route("/wireguard/interfaces/add", methods=['POST'])
@login_required
@setup_required
def add_wireguard_iface():
    from linguard.web.forms import AddInterfaceForm
    form = AddInterfaceForm.from_form(AddInterfaceForm(request.form))
    view = "web/wireguard-add-iface.html"
    context = {
        "title": "Add interface",
        "form": form,

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
            if device == item.uuid:
                datasets["rx"].append(data.rx)
                datasets["tx"].append(data.tx)
                break
    return {"labels": labels, "datasets": datasets}


@router.route("/wireguard/interfaces/<uuid>", methods=['GET', "POST"])
@login_required
@setup_required
def get_wireguard_iface(uuid: str):
    if uuid not in interfaces:
        abort(NOT_FOUND, f"Unknown interface '{uuid}'.")
    iface = interfaces[uuid]
    view = "web/wireguard-iface.html"
    data = load_traffic_data(iface)
    session_data = traffic_config.driver.get_session_data()
    iface_traffic = session_data.get(iface.uuid, TrafficData(0, 0))
    context = {
        "title": "Interface",
        "iface": iface,
        "last_update": datetime.now().strftime("%H:%M"),
        "EMPTY_FIELD": EMPTY_FIELD,
        "chart": {"labels": data["labels"], "datasets": data["datasets"]},
        "iface_traffic": TrafficData(iface_traffic.rx, iface_traffic.tx),
        "session_traffic": session_data,
        "traffic_config": traffic_config
    }
    from linguard.web.forms import EditInterfaceForm
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
        context["success"] = True
        context["success_details"] = "Interface updated successfully."
    except Exception as e:
        log_exception(e)
        context["error"] = True
        context["error_details"] = e
    return ViewController(view, **context).load()


@router.route("/wireguard/interfaces/<uuid>", methods=['DELETE'])
@login_required
@setup_required
def remove_wireguard_iface(uuid: str):
    if uuid not in interfaces:
        abort(NOT_FOUND, f"Interface {uuid} not found.")
    return RestController(uuid).remove_iface()


@router.route("/wireguard/interfaces/<uuid>/<action>", methods=['POST'])
@login_required
@setup_required
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
@setup_required
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
@setup_required
def download_wireguard_iface(uuid: str):
    if uuid not in interfaces.keys():
        error(f"Unknown interface {uuid}")
        abort(NOT_FOUND)
    return RestController().download_iface(interfaces[uuid])


@router.route("/wireguard/peers/add", methods=['GET'])
@login_required
@setup_required
def create_wireguard_peer():
    if len(interfaces) < 1:
        abort(BAD_REQUEST, "There are no wireguard interfaces!")
    iface_uuid = request.args.get("interface", None)
    iface = interfaces.get(iface_uuid, None)
    from linguard.web.forms import AddPeerForm
    form = AddPeerForm.populate(AddPeerForm(), iface)
    context = {
        "title": "Add peer",
        "form": form,

    }
    return ViewController("web/wireguard-add-peer.html", **context).load()


@router.route("/wireguard/peers/add", methods=['POST'])
@login_required
@setup_required
def add_wireguard_peer():
    if len(interfaces) < 1:
        abort(BAD_REQUEST, "There are no wireguard interfaces!")
    from linguard.web.forms import AddPeerForm
    form = AddPeerForm.from_form(AddPeerForm(request.form))
    view = "web/wireguard-add-peer.html"
    context = {
        "title": "Add Peer",
        "form": form,

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
@setup_required
def remove_wireguard_peer(uuid: str):
    peer = get_all_peers().get(uuid, None)
    if not peer:
        raise WireguardError(f"Unknown peer '{uuid}'.", NOT_FOUND)
    return RestController().remove_peer(peer)


@router.route("/wireguard/peers/<uuid>", methods=['GET', "POST"])
@login_required
@setup_required
def get_wireguard_peer(uuid: str):
    peer = get_all_peers().get(uuid, None)
    if not peer:
        raise WireguardError(f"Unknown peer '{uuid}'.", NOT_FOUND)
    view = "web/wireguard-peer.html"
    data = load_traffic_data(peer)
    session_data = traffic_config.driver.get_session_data().get(peer.uuid, TrafficData(0, 0))
    handshake_ago = None
    if session_data.last_handshake:
        handshake_ago = get_time_ago(session_data.last_handshake)
    context = {
        "title": "Peer",
        "peer": peer,
        "last_update": datetime.now().strftime("%H:%M"),
        "EMPTY_FIELD": EMPTY_FIELD,
        "chart": {"labels": data["labels"], "datasets": data["datasets"]},
        "session_traffic": TrafficData(session_data.rx, session_data.tx),
        "handshake_ago": handshake_ago,
        "traffic_config": traffic_config
    }
    from linguard.web.forms import EditPeerForm
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
@setup_required
def download_wireguard_peer(uuid: str):
    peer = get_all_peers().get(uuid, None)
    if not peer:
        msg = f"Unknown peer '{uuid}'."
        error(msg)
        abort(NOT_FOUND, msg)
    return RestController().download_peer(peer)


@router.route("/themes")
@login_required
@setup_required
def themes():
    context = {
        "title": "Themes"
    }
    return ViewController("web/themes.html", **context).load()


@router.route("/settings")
@login_required
@setup_required
def settings():
    from linguard.web.forms import SettingsForm
    form = SettingsForm.new()
    form.traffic_enabled.data = traffic_config.enabled
    form.log_overwrite.data = logger_config.overwrite
    form.traffic_driver_options.data = json.dumps(traffic_config.driver.__to_yaml_dict__(), indent=4, sort_keys=True)
    context = {
        "title": "Settings",
        "form": form,

    }
    return ViewController("web/settings.html", **context).load()


@router.route("/settings", methods=['POST'])
@login_required
@setup_required
def save_settings():
    from linguard.web.forms import SettingsForm
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
        form.web_login_attempts.data = form.web_login_attempts.data or web_config.login_attempts
        form.web_login_ban_time.data = form.web_login_ban_time.data or web_config.login_ban_time

        form.app_endpoint.data = form.app_endpoint.data or wireguard_config.endpoint
        form.app_wg_bin.data = form.app_wg_bin.data or wireguard_config.wg_bin
        form.app_wg_quick_bin.data = form.app_wg_quick_bin.data or wireguard_config.wg_quick_bin
        form.app_iptables_bin.data = form.app_iptables_bin.data or wireguard_config.iptables_bin
        form.app_interfaces_folder.data = form.app_interfaces_folder.data or wireguard_config.interfaces_folder

        form.traffic_driver_options.data = form.traffic_driver_options.data or \
                                           json.dumps(traffic_config.driver.__to_yaml_dict__(), indent=4,
                                                      sort_keys=True)

        context["success"] = True
        context["success_details"] = "Settings updated!"
        context["warning"] = True
        context["warning_details"] = f"You may need to restart {APP_NAME} to apply some changes."
    except Exception as e:
        log_exception(e)
        context["error"] = True
        context["error_details"] = e
    return ViewController(view, **context).load()


@router.route("/setup")
@login_required
def setup():
    if global_properties.setup_file_exists():
        return redirect(request.args.get("next", url_for("router.index")))
    from linguard.web.forms import SetupForm
    form = SetupForm()
    wireguard_config.set_default_endpoint()
    form.app_endpoint.data = wireguard_config.endpoint
    context = {
        "title": "Setup",
        "form": form,
    }
    return ViewController("web/setup.html", **context).load()


@router.route("/setup", methods=['POST'])
@login_required
def apply_setup():
    if global_properties.setup_file_exists():
        abort(BAD_REQUEST, "Setup already performed!")
    from linguard.web.forms import SetupForm
    form = SetupForm(request.form)
    view = "web/setup.html"
    context = {
        "title": "Setup",
        "form": form
    }
    if not form.validate():
        error("Unable to validate form")
        return ViewController(view, **context).load()
    try:
        RestController().apply_setup(form)
        with open(global_properties.setup_filepath, "w") as f:
            f.write("")
        return redirect(request.args.get("next", url_for("router.index")))
    except Exception as e:
        log_exception(e)
        context["error"] = True
        context["error_details"] = e
    return ViewController(view, **context).load()


@router.route("/about", methods=['GET'])
@login_required
@setup_required
def about():
    view = "web/about.html"
    context = {
        "title": "About",
    }
    return ViewController(view, **context).load()


@router.route("/profile", methods=['GET'])
@login_required
@setup_required
def profile():
    from linguard.web.forms import ProfileForm, PasswordResetForm
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
        "login_ago": get_time_ago(current_user.login_date),
    }
    return ViewController(view, **context).load()


@router.route("/profile", methods=['POST'])
@login_required
@setup_required
def save_profile():
    if "new_password" in request.form:
        return password_reset()
    from linguard.web.forms import ProfileForm, PasswordResetForm
    view = "web/profile.html"
    profile_form = ProfileForm(request.form)
    password_reset_form = PasswordResetForm()
    context = {
        "title": "Profile",
        "profile_form": profile_form,
        "password_reset_form": password_reset_form,
        "login_ago": get_time_ago(current_user.login_date),
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
    from linguard.web.forms import PasswordResetForm, ProfileForm
    profile_form = ProfileForm()
    profile_form.username.data = current_user.name
    password_reset_form = PasswordResetForm(request.form)
    context = {
        "title": "Profile",
        "profile_form": profile_form,
        "password_reset_form": password_reset_form,
        "login_ago": get_time_ago(current_user.login_date),
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
            next_url = url_for(request.endpoint)
        except Exception:
            uuid = request.path.rsplit("/", 1)[-1]
            next_url = url_for(request.endpoint, uuid=uuid)
        return redirect(url_for("router.login", next=next_url))
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
