"""Behavioural tests for ``app.services.wireguard.WireGuardService``.

These tests assert the *contract* of the service: the exact command lines it
hands to ``wg``/``ip``/``ifconfig``, the configuration text it produces, and how
it reacts to commands that fail.  ``subprocess.run`` is patched inside the module
under test with realistic ``CompletedProcess`` values; the database is real
(SQLite through the shared fixtures).
"""

import base64
import subprocess
from dataclasses import dataclass

import pytest

from app.services.wireguard import WireGuardService


# ---------------------------------------------------------------------------
# Realistic WireGuard material (44 character base64 keys)
# ---------------------------------------------------------------------------

PRIVATE_KEY = base64.b64encode(bytes([1]) * 32).decode()
PUBLIC_KEY = base64.b64encode(bytes([2]) * 32).decode()
PEER_KEY = base64.b64encode(bytes([3]) * 32).decode()
PEER_KEY_2 = base64.b64encode(bytes([4]) * 32).decode()
PRESHARED_KEY = base64.b64encode(bytes([5]) * 32).decode()


# ---------------------------------------------------------------------------
# subprocess fake
# ---------------------------------------------------------------------------

@dataclass
class Call:
    argv: list
    kwargs: dict


class FakeRunner:
    """Records ``subprocess.run`` calls and answers them from rule table."""

    def __init__(self, default_returncode=0, default_stdout="", default_stderr=""):
        self.calls: list[Call] = []
        self.rules: list[tuple] = []
        self.default = (default_returncode, default_stdout, default_stderr)

    def on(self, matcher, *, returncode=0, stdout="", stderr="", raises=None):
        """Answer calls whose argv contains ``matcher`` (substring or predicate)."""
        if callable(matcher):
            predicate = matcher
        else:
            predicate = lambda argv, m=matcher: m in argv  # noqa: E731
        self.rules.append((predicate, returncode, stdout, stderr, raises))
        return self

    def __call__(self, argv, **kwargs):
        self.calls.append(Call(list(argv), kwargs))
        for predicate, rc, out, err, raises in self.rules:
            if predicate(list(argv)):
                if raises is not None:
                    raise raises
                return subprocess.CompletedProcess(list(argv), rc, out, err)
        rc, out, err = self.default
        return subprocess.CompletedProcess(list(argv), rc, out, err)

    # helpers -------------------------------------------------------------
    @property
    def argv_list(self):
        return [call.argv for call in self.calls]

    def calls_containing(self, word):
        return [c.argv for c in self.calls if word in c.argv]


class FakeFirewall:
    def __init__(self, result=True):
        self.result = result
        self.setup_calls = []
        self.cleanup_calls = []

    def setup_nat(self, interface, ipv4_subnet, ipv6_subnet):
        self.setup_calls.append((interface, ipv4_subnet, ipv6_subnet))
        return self.result

    def cleanup_nat(self, interface, ipv4_subnet, ipv6_subnet):
        self.cleanup_calls.append((interface, ipv4_subnet, ipv6_subnet))
        return True


@pytest.fixture
def firewall():
    return FakeFirewall()


@pytest.fixture
def service(firewall):
    return WireGuardService(wg_binary="wg", firewall_service=firewall)


@pytest.fixture
def runner(monkeypatch):
    fake = FakeRunner()
    monkeypatch.setattr("app.services.wireguard.subprocess.run", fake)
    return fake


@pytest.fixture
def macos_service(firewall, monkeypatch):
    monkeypatch.setattr("app.services.wireguard.platform.system", lambda: "Darwin")
    return WireGuardService(wg_binary="wg", firewall_service=firewall)


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

async def make_server(db, name="srv-a", **kwargs):
    from app.models.server import Server

    server = Server(
        name=name,
        public_key=PUBLIC_KEY,
        private_key=PRIVATE_KEY,
        listen_port=kwargs.pop("listen_port", 51820),
        **kwargs,
    )
    db.add(server)
    await db.commit()
    await db.refresh(server)
    return server


async def make_peer(db, server_id, name="peer-a", **kwargs):
    from app.models.peer import Peer

    peer = Peer(
        server_id=server_id,
        name=name,
        private_key=PRIVATE_KEY,
        public_key=kwargs.pop("public_key", PEER_KEY),
        **kwargs,
    )
    db.add(peer)
    await db.commit()
    await db.refresh(peer)
    return peer


# ===========================================================================
# Key material
# ===========================================================================

class TestKeyOperations:
    def test_should_pipe_private_key_into_pubkey_when_generating_keypair(self, service, runner):
        runner.on("genkey", stdout=f"{PRIVATE_KEY}\n")
        runner.on("pubkey", stdout=f"{PUBLIC_KEY}\n")

        private, public = service.generate_keypair()

        assert (private, public) == (PRIVATE_KEY, PUBLIC_KEY)
        assert runner.argv_list == [["wg", "genkey"], ["wg", "pubkey"]]
        pubkey_call = runner.calls[1]
        assert pubkey_call.kwargs["input"] == PRIVATE_KEY
        assert pubkey_call.kwargs["check"] is True

    def test_should_raise_when_genkey_binary_is_missing(self, service, runner):
        runner.on("genkey", raises=FileNotFoundError("wg not installed"))

        with pytest.raises(FileNotFoundError):
            service.generate_keypair()

    def test_should_generate_preshared_key_with_genpsk(self, service, runner):
        runner.on("genpsk", stdout=f"{PRESHARED_KEY}\n")

        assert service.generate_preshared_key() == PRESHARED_KEY
        assert runner.argv_list == [["wg", "genpsk"]]

    def test_should_send_key_with_trailing_newline_when_deriving_public_key(self, service, runner):
        runner.on("pubkey", stdout=f"{PUBLIC_KEY}\n")

        assert service.derive_public_key(f"  {PRIVATE_KEY}\n") == PUBLIC_KEY
        assert runner.calls[0].argv == ["wg", "pubkey"]
        assert runner.calls[0].kwargs["input"] == PRIVATE_KEY + "\n"

    @pytest.mark.parametrize(
        "bad_key, message",
        [
            ("", "Private key is empty"),
            ("    \n", "Private key is empty after trimming"),
            ("tooshort", "Invalid private key length: 8"),
            ("A" * 44, "should end with '='"),
        ],
    )
    def test_should_reject_malformed_private_keys_without_calling_wg(self, service, runner, bad_key, message):
        with pytest.raises(ValueError, match=message):
            service.derive_public_key(bad_key)
        assert runner.calls == []

    def test_should_wrap_wg_failure_into_value_error_when_deriving(self, service, runner):
        runner.on(
            "pubkey",
            raises=subprocess.CalledProcessError(1, ["wg", "pubkey"], "", "Key is not the correct length or format\n"),
        )

        with pytest.raises(ValueError, match="Failed to derive public key: Key is not the correct length"):
            service.derive_public_key(PRIVATE_KEY)


# ===========================================================================
# sudo helper
# ===========================================================================

class TestRunSudoCommand:
    def test_should_add_non_interactive_flag_and_disable_askpass(self, service, runner):
        service._run_sudo_command(["sudo", "ip", "link", "set", "wg0", "up"])

        argv, kwargs = runner.calls[0].argv, runner.calls[0].kwargs
        assert argv == ["sudo", "-n", "ip", "link", "set", "wg0", "up"]
        assert kwargs["stdin"] is subprocess.DEVNULL
        assert kwargs["env"]["SUDO_ASKPASS"] == "/bin/false"
        assert kwargs["timeout"] == 10

    def test_should_not_duplicate_n_flag_when_already_present(self, service, runner):
        service._run_sudo_command(["sudo", "-n", "iptables", "-L"])

        assert runner.calls[0].argv == ["sudo", "-n", "iptables", "-L"]

    def test_should_pass_input_data_when_stdin_payload_given(self, service, runner):
        service._run_sudo_command(["sudo", "wg", "set", "wg0", "private-key", "/dev/stdin"], input_data=PRIVATE_KEY, timeout=3)

        kwargs = runner.calls[0].kwargs
        assert kwargs["input"] == PRIVATE_KEY
        assert "stdin" not in kwargs
        assert kwargs["timeout"] == 3


# ===========================================================================
# Interface lifecycle primitives
# ===========================================================================

class TestInterfaceCreation:
    def test_should_create_interface_with_ip_link_on_linux(self, service, runner):
        success, interface = service._create_interface("wg0")

        assert (success, interface) == (True, "wg0")
        assert runner.argv_list == [
            ["sudo", "-n", "ip", "link", "add", "dev", "wg0", "type", "wireguard"]
        ]

    def test_should_report_failure_and_keep_name_when_ip_link_fails(self, service, runner):
        runner.on("add", returncode=2, stderr="RTNETLINK answers: Operation not permitted\n")

        success, interface = service._create_interface("wg0")

        assert (success, interface) == (False, "wg0")

    def test_should_return_failure_when_ip_link_raises(self, service, runner):
        runner.on("add", raises=subprocess.CalledProcessError(1, "ip", "", "boom"))

        assert service._create_interface("wg1") == (False, "wg1")

    @pytest.mark.parametrize(
        "requested, expected",
        [("wg0", "utun10"), ("wg3", "utun13"), ("wg-not-a-number", "utun10"), ("en0", "utun10")],
    )
    def test_should_map_interface_names_to_utun_on_macos(self, macos_service, runner, requested, expected):
        runner.on("ifconfig", returncode=1)  # interface does not exist yet

        success, interface = macos_service._create_interface(requested)

        assert (success, interface) == (True, expected)
        assert ["sudo", "-n", "wireguard-go", expected] in runner.argv_list

    def test_should_reuse_existing_wireguard_utun_interface_on_macos(self, macos_service, runner):
        runner.on("ifconfig", returncode=0)
        runner.on("show", returncode=0)

        success, interface = macos_service._create_interface("wg2")

        assert (success, interface) == (True, "utun12")
        assert ["sudo", "-n", "wireguard-go", "utun12"] not in runner.argv_list

    def test_should_skip_non_wireguard_utun_and_take_next_free_on_macos(self, macos_service, runner):
        # utun10 exists but is not a WireGuard interface; utun11 is free.
        def ifconfig(argv):
            return "ifconfig" in argv and argv[-1] in {"utun10"}

        macos_service._run_sudo_command = _fake_sudo_show(returncode=1)
        runner.on(ifconfig, returncode=0)
        runner.on(lambda argv: argv[-1] == "utun11", returncode=1)

        success, interface = macos_service._create_interface("wg0")

        assert (success, interface) == (True, "utun11")


def _fake_sudo_show(returncode):
    """Replace ``_run_sudo_command`` with a stub answering ``wg show`` only."""
    def _run(cmd, input_data=None, timeout=10):
        return subprocess.CompletedProcess(cmd, returncode, "", "not wireguard")

    return _run


class TestInterfaceConfiguration:
    def test_should_set_private_key_then_listen_port(self, service, runner):
        runner.on(lambda argv: argv[:3] == ["sudo", "-n", "wg"] and "show" in argv, returncode=1)  # key not set yet

        assert service._set_interface_config("wg0", PRIVATE_KEY, 51820) is True

        assert runner.argv_list == [
            ["sudo", "-n", "wg", "show", "wg0", "private-key"],
            ["sudo", "-n", "wg", "set", "wg0", "private-key", "/dev/stdin"],
            ["sudo", "-n", "wg", "set", "wg0", "listen-port", "51820"],
        ]
        key_call = runner.calls[1]
        assert key_call.kwargs["input"] == PRIVATE_KEY

    def test_should_not_reapply_key_when_interface_already_has_one(self, service, runner):
        runner.on(lambda argv: "show" in argv, returncode=0)

        assert service._set_interface_config("wg0", PRIVATE_KEY, 51820) is False
        assert len(runner.calls) == 1

    def test_should_report_failure_when_setting_private_key_fails(self, service, runner):
        runner.on(lambda argv: "show" in argv, returncode=1)
        runner.on(lambda argv: "set" in argv and "private-key" in argv, returncode=1, stderr="Unable to modify interface")

        assert service._set_interface_config("wg0", PRIVATE_KEY, 51820) is False
        assert runner.argv_list[-1] == ["sudo", "-n", "wg", "set", "wg0", "private-key", "/dev/stdin"]

    def test_should_report_failure_when_setting_listen_port_fails(self, service, runner):
        runner.on(lambda argv: "show" in argv, returncode=1)
        runner.on("listen-port", returncode=1, stderr="invalid port")

        assert service._set_interface_config("wg0", PRIVATE_KEY, 70000) is False

    def test_should_report_failure_when_subprocess_raises(self, service, runner):
        runner.on(lambda argv: "show" in argv, returncode=1)
        runner.on("set", raises=OSError("sudo missing"))

        assert service._set_interface_config("wg0", PRIVATE_KEY, 51820) is False


class TestInterfaceAddresses:
    def test_should_add_ipv4_and_ipv6_addresses_on_linux(self, service, runner):
        assert service._set_interface_addresses("wg0", "10.8.0.1/24", "fd00::1/64") is True

        assert runner.argv_list == [
            ["sudo", "-n", "ip", "addr", "add", "10.8.0.1/24", "dev", "wg0"],
            ["sudo", "-n", "ip", "addr", "add", "fd00::1/64", "dev", "wg0"],
        ]

    def test_should_skip_address_commands_when_addresses_absent(self, service, runner):
        assert service._set_interface_addresses("wg0", None, None) is True
        assert runner.calls == []

    def test_should_stop_after_failed_ipv4_assignment(self, service, runner):
        runner.on("addr", returncode=2, stderr="RTNETLINK answers: File exists")

        assert service._set_interface_addresses("wg0", "10.8.0.1/24", "fd00::1/64") is False
        assert len(runner.calls) == 1

    def test_should_use_ifconfig_hex_netmask_on_macos(self, macos_service, runner):
        assert macos_service._set_interface_addresses("utun10", "10.8.0.1/24", "fd00::1/64") is True

        assert runner.argv_list == [
            ["sudo", "-n", "ifconfig", "utun10", "inet", "10.8.0.1", "10.8.0.1", "netmask", "0xffffff00"],
            ["sudo", "-n", "ifconfig", "utun10", "inet6", "fd00::1/64"],
        ]

    def test_should_return_false_when_address_command_raises(self, service, runner):
        runner.on("addr", raises=subprocess.CalledProcessError(1, "ip", "", "boom"))

        assert service._set_interface_addresses("wg0", "10.8.0.1/24", None) is False


class TestInterfaceUp:
    def test_should_bring_linux_interface_up(self, service, runner):
        assert service._bring_interface_up("wg0") is True
        assert runner.argv_list == [["sudo", "-n", "ip", "link", "set", "wg0", "up"]]

    def test_should_report_failure_when_link_set_up_fails(self, service, runner):
        runner.on("up", returncode=1, stderr="Cannot find device \"wg0\"")

        assert service._bring_interface_up("wg0") is False

    def test_should_bring_macos_interface_up_with_ifconfig(self, macos_service, runner):
        assert macos_service._bring_interface_up("utun10") is True
        assert runner.argv_list == [["sudo", "-n", "ifconfig", "utun10", "up"]]


class TestPeerCommands:
    def test_should_pass_allowed_ips_and_raw_keepalive_to_wg_set(self, service, runner):
        assert service._add_peer("wg0", {
            "public_key": PEER_KEY,
            "allowed_ips": "10.8.0.2/32, fd00::2/128",
            "persistent_keepalive": 25,
        }) is True

        assert runner.argv_list == [
            ["sudo", "-n", "wg", "set", "wg0", "peer", PEER_KEY,
             "allowed-ips", "10.8.0.2/32, fd00::2/128"],
            ["sudo", "-n", "wg", "set", "wg0", "peer", PEER_KEY,
             "persistent-keepalive", "25"],
        ]

    def test_should_feed_preshared_key_over_stdin(self, service, runner):
        assert service._add_peer("wg0", {
            "public_key": PEER_KEY,
            "allowed_ips": "10.8.0.2/32",
            "preshared_key": PRESHARED_KEY,
        }) is True

        assert runner.argv_list[0][-2:] == ["preshared-key", "/dev/stdin"]
        assert runner.calls[0].kwargs["input"] == PRESHARED_KEY
        assert not any("persistent-keepalive" in argv for argv in runner.argv_list)

    def test_should_report_failure_when_wg_set_rejects_the_peer(self, service, runner):
        runner.on("peer", returncode=1, stderr="Unable to modify interface: Invalid argument")

        assert service._add_peer("wg0", {"public_key": PEER_KEY, "allowed_ips": "10.8.0.2/32"}) is False

    def test_should_remove_every_peer_reported_by_wg_show(self, service, runner):
        runner.on("peers", stdout=f"{PEER_KEY}\n{PEER_KEY_2}\n")

        assert service._remove_all_peers("wg0") is True

        assert runner.argv_list == [
            ["sudo", "-n", "wg", "show", "wg0", "peers"],
            ["sudo", "-n", "wg", "set", "wg0", "peer", PEER_KEY, "remove"],
            ["sudo", "-n", "wg", "set", "wg0", "peer", PEER_KEY_2, "remove"],
        ]

    def test_should_not_issue_remove_commands_when_no_peers_exist(self, service, runner):
        runner.on("peers", stdout="\n")

        assert service._remove_all_peers("wg0") is True
        assert runner.argv_list == [["sudo", "-n", "wg", "show", "wg0", "peers"]]

    def test_should_return_false_when_listing_peers_raises(self, service, runner):
        runner.on("peers", raises=subprocess.TimeoutExpired("wg", 10))

        assert service._remove_all_peers("wg0") is False


# ===========================================================================
# Full server lifecycle (database driven)
# ===========================================================================

def fresh_interface(runner):
    """Make ``wg show <iface> private-key`` answer "no key yet" (new interface)."""
    runner.on(lambda argv: argv[:3] == ["sudo", "-n", "wg"] and "show" in argv
              and argv[-1] == "private-key", returncode=1)
    runner.on(lambda argv: argv[:3] == ["sudo", "-n", "wg"] and "show" in argv
              and argv[-1] == "peers", stdout="")
    return runner


class TestStartInterface:
    async def test_should_configure_interface_and_add_enabled_peers(self, service, runner, firewall, db_session):
        fresh_interface(runner)
        server = await make_server(db_session, ipv4_address="10.8.0.1/24", ipv6_address="fd00::1/64")
        await make_peer(db_session, server.id, "alice", ipv4_address="10.8.0.2", ipv6_address="fd00::2/128",
                        preshared_key=PRESHARED_KEY, persistent_keepalive=25)
        await make_peer(db_session, server.id, "bob", public_key=PEER_KEY_2, ipv4_address="10.8.0.3/32")
        await make_peer(db_session, server.id, "disabled", public_key=PEER_KEY, ipv4_address="10.8.0.4", enabled=False)

        assert await service.start_interface(db_session, server.id, "wg0") is True

        assert firewall.setup_calls == [("wg0", "10.8.0.1/24", "fd00::1/64")]
        peer_calls = [argv for argv in runner.argv_list if argv[5:6] == ["peer"]]
        assert peer_calls == [
            ["sudo", "-n", "wg", "set", "wg0", "peer", PEER_KEY,
             "allowed-ips", "10.8.0.2/32, fd00::2/128", "preshared-key", "/dev/stdin"],
            ["sudo", "-n", "wg", "set", "wg0", "peer", PEER_KEY, "persistent-keepalive", "25"],
            ["sudo", "-n", "wg", "set", "wg0", "peer", PEER_KEY_2, "allowed-ips", "10.8.0.3/32"],
            ["sudo", "-n", "wg", "set", "wg0", "peer", PEER_KEY_2, "persistent-keepalive", "25"],
        ]

    async def test_should_skip_peers_without_addresses(self, service, runner, db_session):
        fresh_interface(runner)
        server = await make_server(db_session, ipv4_address="10.8.0.1/24")
        await make_peer(db_session, server.id, "no-ip")

        assert await service.start_interface(db_session, server.id, "wg0") is True
        assert not [argv for argv in runner.argv_list if argv[5:6] == ["peer"]]

    async def test_should_return_false_when_server_does_not_exist(self, service, runner, db_session):
        assert await service.start_interface(db_session, 999, "wg0") is False
        assert runner.calls == []

    async def test_should_stop_when_interface_cannot_be_created(self, service, runner, db_session):
        server = await make_server(db_session)
        runner.on("add", returncode=1, stderr="exists")

        assert await service.start_interface(db_session, server.id, "wg0") is False

    async def test_should_tear_interface_down_when_nat_setup_fails(self, service, runner, db_session, firewall):
        fresh_interface(runner)
        firewall.result = False
        server = await make_server(db_session, ipv4_address="10.8.0.1/24")

        assert await service.start_interface(db_session, server.id, "wg0") is False

        assert firewall.cleanup_calls == [("wg0", "10.8.0.1/24", None)]
        assert ["sudo", "-n", "ip", "link", "delete", "wg0"] in runner.argv_list


class TestStopInterface:
    def test_should_bring_interface_down_and_delete_it_on_linux(self, service, runner, firewall):
        assert service.stop_interface("wg0", "10.8.0.1/24", None) is True

        assert runner.argv_list == [
            ["sudo", "-n", "ip", "link", "set", "wg0", "down"],
            ["sudo", "-n", "ip", "link", "delete", "wg0"],
        ]
        assert firewall.cleanup_calls == [("wg0", "10.8.0.1/24", None)]

    def test_should_not_delete_interface_when_bringing_down_fails(self, service, runner):
        runner.on("down", returncode=1, stderr="Cannot find device \"wg0\"")

        assert service.stop_interface("wg0") is False
        assert ["sudo", "-n", "ip", "link", "delete", "wg0"] not in runner.argv_list

    def test_should_skip_nat_cleanup_when_no_subnets_given(self, service, runner, firewall):
        assert service.stop_interface("wg0") is True
        assert firewall.cleanup_calls == []

    def test_should_remove_peers_and_ifconfig_down_on_macos(self, macos_service, runner):
        runner.on("peers", stdout=f"{PEER_KEY}\n")

        assert macos_service.stop_interface("utun10") is True

        assert runner.argv_list == [
            ["sudo", "-n", "wg", "show", "utun10", "peers"],
            ["sudo", "-n", "wg", "set", "utun10", "peer", PEER_KEY, "remove"],
            ["sudo", "-n", "ifconfig", "utun10", "down"],
        ]

    def test_should_return_false_when_delete_raises(self, service, runner):
        runner.on("delete", raises=OSError("no such device"))

        assert service.stop_interface("wg0") is False


class TestReloadInterface:
    async def test_should_replace_peers_on_reload(self, service, runner, db_session):
        server = await make_server(db_session)
        await make_peer(db_session, server.id, "alice", ipv4_address="10.8.0.2")
        await make_peer(db_session, server.id, "disabled", public_key=PEER_KEY_2, ipv4_address="10.8.0.3", enabled=False)
        runner.on(lambda argv: "peers" in argv, stdout=f"{PEER_KEY_2}\n")

        assert await service.reload_interface(db_session, server.id, "wg0") is True

        assert runner.argv_list == [
            ["sudo", "-n", "wg", "show", "wg0", "peers"],
            ["sudo", "-n", "wg", "set", "wg0", "peer", PEER_KEY_2, "remove"],
            ["sudo", "-n", "wg", "set", "wg0", "peer", PEER_KEY, "allowed-ips", "10.8.0.2/32"],
            ["sudo", "-n", "wg", "set", "wg0", "peer", PEER_KEY, "persistent-keepalive", "25"],
        ]

    async def test_should_abort_reload_when_peer_removal_fails(self, service, runner, db_session):
        server = await make_server(db_session)
        await make_peer(db_session, server.id, "alice", ipv4_address="10.8.0.2")
        runner.on(lambda argv: "peers" in argv, raises=subprocess.CalledProcessError(1, "wg", "", "fail"))

        assert await service.reload_interface(db_session, server.id, "wg0") is False


# ===========================================================================
# Status / discovery
# ===========================================================================

WG_SHOW_ALL = """interface: wg0
  public key: {pub0}
  private key: (hidden)
  listening port: 51820

interface: wg1
  public key: {pub1}
  listening port: 51821
""".format(pub0=PUBLIC_KEY, pub1=PEER_KEY)


class TestInterfaceStatus:
    def test_should_report_running_with_raw_wg_output(self, service, runner):
        runner.on("show", stdout=f"interface: wg0\n  public key: {PUBLIC_KEY}\n")

        status = service.get_interface_status("wg0")

        assert status == {"status": "running", "output": f"interface: wg0\n  public key: {PUBLIC_KEY}\n"}
        assert runner.argv_list == [["sudo", "-n", "wg", "show", "wg0"]]

    def test_should_report_stopped_when_wg_show_fails(self, service, runner):
        runner.on("show", returncode=1, stderr='Unable to access interface: No such device')

        assert service.get_interface_status("wg0") == {"status": "stopped", "output": ""}

    def test_should_detect_up_interface_from_ip_link_flags(self, service, runner):
        runner.on("ip", stdout="3: wg0: <POINTOPOINT,NOARP,UP,LOWER_UP> mtu 1420 qdisc noqueue state UNKNOWN\n")

        assert service._is_interface_up("wg0") is True
        assert runner.argv_list == [["ip", "link", "show", "wg0"]]

    def test_should_not_confuse_lower_up_flag_with_up(self, service, runner):
        runner.on("ip", stdout="3: wg0: <POINTOPOINT,NOARP,LOWER_UP> mtu 1420\n")

        assert service._is_interface_up("wg0") is False

    def test_should_return_false_when_link_is_missing(self, service, runner):
        runner.on("ip", returncode=1, stderr="Device \"wg0\" does not exist.")

        assert service._is_interface_up("wg0") is False

    def test_should_detect_macos_up_flag_line(self, macos_service, runner):
        runner.on("ifconfig", stdout="utun10: flags=8051<UP,POINTOPOINT,RUNNING,MULTICAST> mtu 1420\n")

        assert macos_service._is_interface_up("utun10") is True

    def test_should_return_false_when_flag_probe_raises(self, service, runner):
        runner.on("ip", raises=OSError("ip missing"))

        assert service._is_interface_up("wg0") is False

    def test_should_only_list_interfaces_that_are_up(self, service, runner):
        runner.on("all", stdout=WG_SHOW_ALL)
        # wg0 is up (ip link), wg1 is present in wg but not UP in the kernel
        runner.on(lambda argv: argv[:3] == ["ip", "link", "show"] and argv[-1] == "wg0",
                 stdout="3: wg0: <POINTOPOINT,NOARP,UP,LOWER_UP>\n")
        runner.on(lambda argv: argv[:3] == ["ip", "link", "show"] and argv[-1] == "wg1",
                 returncode=1)

        assert service.get_all_interfaces() == [{"interface": "wg0", "public_key": PUBLIC_KEY}]
        assert runner.argv_list[0] == ["sudo", "-n", "wg", "show", "all"]

    def test_should_return_empty_list_when_wg_show_all_fails(self, service, runner):
        runner.on("all", raises=subprocess.CalledProcessError(1, "wg"))

        assert service.get_all_interfaces() == []

    def test_should_return_empty_list_when_sudo_times_out(self, service, runner):
        runner.on("all", raises=subprocess.TimeoutExpired("wg", 10))

        assert service.get_all_interfaces() == []

    def test_should_find_interface_by_public_key(self, service, runner):
        runner.on("all", stdout=WG_SHOW_ALL)
        runner.on("ip", stdout="<POINTOPOINT,NOARP,UP,LOWER_UP>")

        assert service.find_interface_by_public_key(PEER_KEY) == "wg1"
        assert service.find_interface_by_public_key(PRESHARED_KEY) is None

    @pytest.mark.parametrize(
        "running, expected",
        [([], "wg0"), (["wg0"], "wg1"), (["wg0", "wg2"], "wg1"), (["wg0", "wg1", "wg2"], "wg3")],
    )
    def test_should_pick_lowest_free_interface_number(self, service, runner, running, expected):
        output = "".join(
            f"interface: {name}\n  public key: {PUBLIC_KEY}\n\n" for name in running
        )
        runner.on("all", stdout=output)
        runner.on("ip", stdout="<POINTOPOINT,NOARP,UP,LOWER_UP>")

        assert service.get_next_available_interface() == expected

    def test_should_use_custom_prefix_when_allocating_interface(self, service, runner):
        runner.on("all", stdout=f"interface: utun10\n  public key: {PUBLIC_KEY}\n")
        runner.on("ip", stdout="<UP>")

        assert service.get_next_available_interface(prefix="utun") == "utun0"


# ===========================================================================
# Configuration generation
# ===========================================================================

class TestConfigGeneration:
    def test_should_produce_exact_server_config_with_peer_options(self, service):
        text = service.generate_config_file(
            interface="wg0",
            private_key=PRIVATE_KEY,
            address="10.8.0.1/24, fd00::1/64",
            listen_port=51820,
            peers=[
                {
                    "public_key": PEER_KEY,
                    "allowed_ips": "10.8.0.2/32, fd00::2/128",
                    "preshared_key": PRESHARED_KEY,
                    "persistent_keepalive": 25,
                },
                {"public_key": PEER_KEY_2, "allowed_ips": "10.8.0.3/32"},
            ],
        )

        assert text == (
            "[Interface]\n"
            f"PrivateKey = {PRIVATE_KEY}\n"
            "Address = 10.8.0.1/24, fd00::1/64\n"
            "ListenPort = 51820\n"
            "\n"
            "[Peer]\n"
            f"PublicKey = {PEER_KEY}\n"
            f"PresharedKey = {PRESHARED_KEY}\n"
            "AllowedIPs = 10.8.0.2/32, fd00::2/128\n"
            "PersistentKeepalive = 25\n"
            "\n"
            "[Peer]\n"
            f"PublicKey = {PEER_KEY_2}\n"
            "AllowedIPs = 10.8.0.3/32\n"
            "\n"
        )

    def test_should_produce_crlf_peer_config_with_dns_and_psk(self, service):
        text = service.generate_peer_config(
            private_key=PRIVATE_KEY,
            address="10.8.0.2/32, fd00::2/128",
            dns="1.1.1.1, 9.9.9.9",
            server_public_key=PUBLIC_KEY,
            server_endpoint="vpn.example.com:51820",
            server_port=51820,
            allowed_ips="0.0.0.0/0, ::/0",
            persistent_keepalive=25,
            preshared_key=PRESHARED_KEY,
        )

        lines = text.split("\r\n")
        assert text.count("\n") == text.count("\r\n")  # CRLF only
        assert lines[:5] == [
            "[Interface]",
            "# WireGuard peer configuration",
            "# Generated by WireGuardService",
            f"PrivateKey = {PRIVATE_KEY}",
            "# Server endpoint",
        ]
        assert "Address = 10.8.0.2/32, fd00::2/128" in lines
        assert f"PresharedKey = {PRESHARED_KEY}" in lines
        assert "Endpoint = vpn.example.com:51820" in lines
        assert "DNS = 1.1.1.1, 9.9.9.9" in lines
        assert lines[-2:] == ["AllowedIPs = 0.0.0.0/0, ::/0", "PersistentKeepalive = 25"]

    def test_should_omit_dns_and_psk_sections_when_not_configured(self, service):
        text = service.generate_peer_config(
            private_key=PRIVATE_KEY,
            address="10.8.0.2/32",
            dns=None,
            server_public_key=PUBLIC_KEY,
            server_endpoint="vpn.example.com:51820",
            server_port=51820,
        )

        assert "DNS =" not in text
        assert "PresharedKey" not in text
        assert "PersistentKeepalive = 25" in text  # default keepalive

    async def test_should_build_server_config_from_database(self, service, db_session):
        server = await make_server(db_session, interface="wg7", ipv4_address="10.9.0.1/24",
                                   ipv6_address="fd00:9::1/64", listen_port=51900)
        await make_peer(db_session, server.id, "alice", ipv4_address="10.9.0.2", ipv6_address="fd00:9::2",
                        preshared_key=PRESHARED_KEY)
        await make_peer(db_session, server.id, "off", public_key=PEER_KEY_2, ipv4_address="10.9.0.3", enabled=False)

        text = await service.generate_server_config(db_session, server.id)

        assert text == (
            "[Interface]\n"
            f"PrivateKey = {PRIVATE_KEY}\n"
            "Address = 10.9.0.1/24, fd00:9::1/64\n"
            "ListenPort = 51900\n"
            "\n"
            "[Peer]\n"
            f"PublicKey = {PEER_KEY}\n"
            f"PresharedKey = {PRESHARED_KEY}\n"
            "AllowedIPs = 10.9.0.2/32, fd00:9::2/128\n"
            "PersistentKeepalive = 25\n"
            "\n"
        )

    async def test_should_fall_back_to_default_interface_when_server_has_none(self, service, db_session):
        server = await make_server(db_session, ipv4_address="10.9.0.1/24")

        text = await service.generate_server_config(db_session, server.id)

        assert "ListenPort = 51820" in text

    async def test_should_raise_when_server_missing_for_config(self, service, db_session):
        with pytest.raises(ValueError, match="Server 4242 not found"):
            await service.generate_server_config(db_session, 4242)


class TestPeerConfigFromDb:
    async def test_should_use_dns_hierarchy_and_peer_routes(self, db_session, seeded_db):
        from sqlalchemy import select as sa_select

        from app.models.settings import GlobalSettings

        settings = (await db_session.execute(sa_select(GlobalSettings))).scalar_one()
        settings.dns_primary = "10.8.0.1"
        await db_session.commit()

        server = await make_server(db_session, ipv4_address="10.8.0.1/24",
                                   endpoint="vpn.example.com", listen_port=51820,
                                   dns_primary="10.8.0.1")
        peer = await make_peer(db_session, server.id, "alice", ipv4_address="10.8.0.2/32",
                               ipv6_address="fd00::2", preshared_key=PRESHARED_KEY,
                               ipv4_allowed_ips="192.168.1.0/24")
        await db_session.commit()

        from app.services.dns_hierarchy import DNSHierarchyService

        service = WireGuardService(wg_binary="wg", firewall_service=FakeFirewall(),
                                   dns_hierarchy_service=DNSHierarchyService())

        text = await service.generate_peer_config_from_db(db_session, peer.id)

        assert "Address = 10.8.0.2/32, fd00::2/128" in text
        assert "DNS = 10.8.0.1" in text
        assert "AllowedIPs = 192.168.1.0/24" in text
        assert f"PresharedKey = {PRESHARED_KEY}" in text
        assert "Endpoint = vpn.example.com" in text

    async def test_should_default_to_full_tunnel_when_peer_has_no_routes(self, service, db_session):
        server = await make_server(db_session, ipv4_address="10.8.0.1/24", endpoint="vpn.example.com")
        peer = await make_peer(db_session, server.id, "alice", ipv4_address="10.8.0.2")

        text = await service.generate_peer_config_from_db(db_session, peer.id)

        assert "AllowedIPs = 0.0.0.0/0, ::/0" in text
        assert "DNS =" not in text

    async def test_should_raise_when_peer_has_no_address(self, service, db_session):
        server = await make_server(db_session)
        peer = await make_peer(db_session, server.id, "alice")

        with pytest.raises(ValueError, match=f"Peer {peer.id} has no IP address configured"):
            await service.generate_peer_config_from_db(db_session, peer.id)

    async def test_should_raise_when_peer_missing(self, service, db_session):
        with pytest.raises(ValueError, match="Peer 999 not found"):
            await service.generate_peer_config_from_db(db_session, 999)


# ===========================================================================
# Construction
# ===========================================================================

class TestConstruction:
    def test_should_build_dummy_firewall_service_when_none_injected(self):
        service = WireGuardService(wg_binary="wg")

        from app.services.firewall.dummy_driver import DummyFirewallDriver

        # pytest.ini exports DEBUG_BYPASS_FIREWALL=true for local test runs
        assert isinstance(service.firewall_service.driver, DummyFirewallDriver)

    def test_should_remember_binary_and_platform(self, monkeypatch):
        monkeypatch.setattr("app.services.wireguard.platform.system", lambda: "Darwin")

        service = WireGuardService(wg_binary="/usr/local/bin/wg", firewall_service=FakeFirewall())

        assert service.wg_binary == "/usr/local/bin/wg"
        assert service.is_macos is True


# ===========================================================================
# Error handling of individual steps
# ===========================================================================

class TestStepFailures:
    def test_should_report_failure_when_config_step_raises_called_process_error(self, service, runner):
        runner.on("show", raises=subprocess.CalledProcessError(1, "wg", "", "permission denied"))

        assert service._set_interface_config("wg0", PRIVATE_KEY, 51820) is False

    @pytest.mark.parametrize("exc", [subprocess.CalledProcessError(1, "ip", "", "boom"), OSError("ip missing")])
    def test_should_report_failure_when_address_step_raises(self, service, runner, exc):
        runner.on("addr", raises=exc)

        assert service._set_interface_addresses("wg0", "10.8.0.1/24", None) is False

    @pytest.mark.parametrize("exc", [subprocess.CalledProcessError(1, "ip", "", "boom"), OSError("ip missing")])
    def test_should_report_failure_when_bring_up_raises(self, service, runner, exc):
        runner.on("up", raises=exc)

        assert service._bring_interface_up("wg0") is False

    @pytest.mark.parametrize("exc", [subprocess.CalledProcessError(1, "wg", "", "boom"), OSError("wg missing")])
    def test_should_report_failure_when_add_peer_raises(self, service, runner, exc):
        runner.on("set", raises=exc)

        assert service._add_peer("wg0", {"public_key": PEER_KEY, "allowed_ips": "10.8.0.2/32"}) is False

    async def test_should_stop_after_config_failure_when_starting(self, service, runner, db_session):
        fresh_interface(runner)
        runner.on("listen-port", returncode=1, stderr="bad port")
        server = await make_server(db_session, ipv4_address="10.8.0.1/24")

        assert await service.start_interface(db_session, server.id, "wg0") is False
        assert not [argv for argv in runner.argv_list if "addr" in argv]

    async def test_should_stop_after_address_failure_when_starting(self, service, runner, db_session):
        fresh_interface(runner)
        runner.on("addr", returncode=1, stderr="File exists")
        server = await make_server(db_session, ipv4_address="10.8.0.1/24")

        assert await service.start_interface(db_session, server.id, "wg0") is False
        assert not [argv for argv in runner.argv_list if "up" in argv]

    async def test_should_stop_after_link_up_failure_when_starting(self, service, runner, db_session):
        fresh_interface(runner)
        runner.on("up", returncode=1, stderr="Cannot assign requested address")
        server = await make_server(db_session, ipv4_address="10.8.0.1/24")

        assert await service.start_interface(db_session, server.id, "wg0") is False
        assert not [argv for argv in runner.argv_list if "set" in argv and "peer" in argv]

    async def test_should_keep_going_when_a_peer_fails_to_be_added(self, service, runner, db_session):
        fresh_interface(runner)
        runner.on(lambda argv: argv[5:6] == ["peer"] and PEER_KEY_2 in argv, returncode=1, stderr="bad key")
        server = await make_server(db_session, ipv4_address="10.8.0.1/24")
        await make_peer(db_session, server.id, "bad", public_key=PEER_KEY_2, ipv4_address="10.8.0.2")

        assert await service.start_interface(db_session, server.id, "wg0") is True

    async def test_should_return_false_when_reload_raises(self, service, runner, db_session):
        server = await make_server(db_session)
        service._remove_all_peers = lambda interface: (_ for _ in ()).throw(RuntimeError("db down"))

        assert await service.reload_interface(db_session, server.id, "wg0") is False

    def test_should_return_false_when_macos_ifconfig_down_fails(self, macos_service, runner):
        runner.on("peers", stdout="")
        runner.on("down", returncode=1)

        assert macos_service.stop_interface("utun10") is False

    def test_should_return_false_when_linux_delete_fails(self, service, runner):
        runner.on("delete", returncode=1, stderr="busy")

        assert service.stop_interface("wg0") is False

    def test_should_return_empty_list_on_unexpected_wg_error(self, service, runner):
        runner.on("all", raises=RuntimeError("unexpected"))

        assert service.get_all_interfaces() == []


class TestMacStatusDetails:
    def test_should_return_false_when_ifconfig_fails_on_macos(self, macos_service, runner):
        runner.on("ifconfig", returncode=1)

        assert macos_service._is_interface_up("utun10") is False

    def test_should_return_false_when_macos_flags_lack_up(self, macos_service, runner):
        runner.on("ifconfig", stdout="utun10: flags=8050<POINTOPOINT,RUNNING,MULTICAST> mtu 1420\n")

        assert macos_service._is_interface_up("utun10") is False

    def test_should_ignore_interface_names_without_numeric_suffix(self, service, runner):
        runner.on("all", stdout=(
            f"interface: wgshare\n  public key: {PUBLIC_KEY}\n\n"
            f"interface: wg1\n  public key: {PEER_KEY}\n"
        ))
        runner.on("ip", stdout="<POINTOPOINT,NOARP,UP,LOWER_UP>")

        assert service.get_next_available_interface() == "wg0"


class TestPeerConfigOptionalParts:
    async def test_should_render_secondary_dns_and_combined_routes(self, db_session):
        class StubDns:
            async def resolve_dns_for_peer(self, db, peer_id):
                return "1.1.1.1", "9.9.9.9"

        server = await make_server(db_session, ipv4_address="10.8.0.1/24",
                                   endpoint="vpn.example.com")
        peer = await make_peer(db_session, server.id, "alice", ipv4_address="10.8.0.2",
                               ipv6_address="fd00::2/128",
                               ipv4_allowed_ips="192.168.0.0/16", ipv6_allowed_ips="fd00:1::/64")
        service = WireGuardService(wg_binary="wg", firewall_service=FakeFirewall(),
                                   dns_hierarchy_service=StubDns())

        text = await service.generate_peer_config_from_db(db_session, peer.id)

        assert "DNS = 1.1.1.1, 9.9.9.9" in text
        assert "Address = 10.8.0.2/32, fd00::2/128" in text
        assert "AllowedIPs = 192.168.0.0/16, fd00:1::/64" in text

    async def test_should_report_failure_when_dns_hierarchy_raises(self, db_session):
        class BrokenDns:
            async def resolve_dns_for_peer(self, db, peer_id):
                raise RuntimeError("dns lookup failed")

        server = await make_server(db_session, ipv4_address="10.8.0.1/24")
        peer = await make_peer(db_session, server.id, "alice", ipv4_address="10.8.0.2")
        service = WireGuardService(wg_binary="wg", firewall_service=FakeFirewall(),
                                   dns_hierarchy_service=BrokenDns())

        with pytest.raises(RuntimeError, match="dns lookup failed"):
            await service.generate_peer_config_from_db(db_session, peer.id)


class TestRemainingBranches:
    def test_should_report_failure_when_ipv6_assignment_fails_after_ipv4(self, service, runner):
        runner.on("fd00::1/64", returncode=2, stderr="RTNETLINK answers: Permission denied")

        assert service._set_interface_addresses("wg0", "10.8.0.1/24", "fd00::1/64") is False
        assert runner.argv_list[-1] == ["sudo", "-n", "ip", "addr", "add", "fd00::1/64", "dev", "wg0"]

    async def test_should_log_but_continue_when_reload_peer_add_fails(self, service, runner, db_session):
        server = await make_server(db_session)
        await make_peer(db_session, server.id, "alice", ipv4_address="10.8.0.2")
        runner.on(lambda argv: "peers" in argv, stdout="")
        runner.on(lambda argv: argv[5:6] == ["peer"], returncode=1, stderr="Invalid argument")

        assert await service.reload_interface(db_session, server.id, "wg0") is True

    async def test_should_skip_dns_lookup_when_no_hierarchy_service_configured(
            self, service, db_session):
        server = await make_server(db_session, ipv4_address="10.8.0.1/24", dns_primary="1.1.1.1")
        peer = await make_peer(db_session, server.id, "alice", ipv4_address="10.8.0.2")

        text = await service.generate_peer_config_from_db(db_session, peer.id)

        assert "DNS =" not in text
