"""Coverage for IP completion and the related Click commands."""

import ipaddress

import pytest
from click.testing import CliRunner

from linguard_cli.completers import (
    IPCompleter,
    dns_command,
    ip_command,
    peer_command,
    port_command,
    subnet_command,
)
from linguard_cli.main import cli


@pytest.fixture
def runner():
    return CliRunner()


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("192.168.1.1", True),
        ("0.0.0.0", True),
        ("255.255.255.255", True),
        ("192.168.1.42/24", True),
        ("10.0.0.1/32", True),
        ("", False),
        ("192.168.1", False),
        ("256.0.0.1", False),
        ("192.168.1.1/33", False),
        ("192.168.1.1//24", False),
        ("fd00::1", False),
        ("not-an-ip", False),
    ],
)
def test_validate_ipv4_and_networks(value, expected):
    assert IPCompleter._is_valid_ip(value) is expected


def test_default_ip_suggestions_include_common_and_sequential_addresses():
    suggestions = IPCompleter.suggest_ips()
    assert suggestions[:20] == [f"203.0.113.{i}" for i in range(1, 21)]
    assert suggestions[20:25] == [f"10.0.0.{i}" for i in range(2, 7)]
    assert suggestions[25:] == [f"192.168.1.{i}" for i in range(2, 7)]
    assert all(ipaddress.IPv4Address(ip) for ip in suggestions)


@pytest.mark.parametrize("prefix", [None, "", "10"])
def test_missing_or_short_prefix_uses_default_suggestions(prefix):
    assert IPCompleter.suggest_ips(prefix, min_length=3) == IPCompleter.suggest_ips()


@pytest.mark.parametrize(
    ("prefix", "expected"),
    [
        ("10.0.0", [f"10.0.0.{i}" for i in range(2, 7)]),
        ("10.0.0.1", [f"10.0.0.{i}" for i in range(2, 7)]),
        ("10.0.0.254", ["10.0.0.255", "10.0.1.0", "10.0.1.1", "10.0.1.2", "10.0.1.3"]),
        ("10.0", []),
        ("10.0.0.", []),
        ("bad", []),
        ("256.0.0.1", []),
    ],
)
def test_sequential_ip_generation(prefix, expected):
    assert IPCompleter._generate_sequential_ips(prefix) == expected
    cidrs = [f"{prefix}{mask}" for mask in IPCompleter.COMMON_SUBNETS] if IPCompleter._is_valid_ip(prefix) else []
    assert IPCompleter.suggest_ips(prefix) == cidrs + expected


@pytest.mark.parametrize(
    ("prefix", "expected"),
    [
        ("10.0.0.1", [f"10.0.0.{i}" for i in range(2, 7)]),
        ("192.168.0.254", ["192.168.0.255", "192.168.1.0", "192.168.1.1", "192.168.1.2", "192.168.1.3"]),
        ("invalid", []),
        ("10.0.0", []),
        ("255.255.255.254", ["255.255.255.255"]),
        ("255.255.255.253", ["255.255.255.254", "255.255.255.255"]),
        ("255.255.255.255", []),
    ],
)
def test_ipv4_generation(prefix, expected):
    assert IPCompleter._generate_ipv4(prefix) == expected


def test_ipv4_generation_preserves_rollover_addresses():
    assert IPCompleter._generate_ipv4("192.168.0.254") == [
        "192.168.0.255", "192.168.1.0", "192.168.1.1", "192.168.1.2", "192.168.1.3"
    ]


def test_sequential_ips_stop_at_end_of_ipv4_space():
    assert IPCompleter._generate_sequential_ips("255.255.255.253") == [
        "255.255.255.254",
        "255.255.255.255",
    ]
    assert IPCompleter._generate_sequential_ips("255.255.255.255") == []


@pytest.mark.parametrize("prefix", ["fd", "FD12", "fd00::"])
def test_ula_prefix_suggests_ipv6_addresses(prefix):
    assert IPCompleter.suggest_ips(prefix) == [
        value
        for i in range(1, 5)
        for value in (f"fd00::{i}:1", f"fd00::1/{i}")
    ]


def test_other_ipv6_prefix_has_no_suggestions():
    assert IPCompleter._suggest_ipv6("2001:db8::") == []
    assert IPCompleter.suggest_ips("2001:db8::") == []


def test_full_ipv4_prefix_includes_cidr_suggestions():
    suggestions = IPCompleter.suggest_ips("10.0.0.1")
    assert suggestions[:len(IPCompleter.COMMON_SUBNETS)] == [
        f"10.0.0.1{mask}" for mask in IPCompleter.COMMON_SUBNETS
    ]
    assert all(IPCompleter._is_valid_ip(value) for value in suggestions)


def test_common_ips_are_bounded_and_valid():
    ips = IPCompleter._generate_common_ips()
    assert ips == [f"203.0.113.{i}" for i in range(1, 21)]
    assert len(set(ips)) == 20
    assert all(ipaddress.IPv4Address(ip) for ip in ips)


@pytest.mark.parametrize(
    ("provider", "expected"),
    [
        ("cloudflare", ["1.1.1.1", "1.0.0.1", "2606:4700:4700::1111", "2606:4700:4700::1001"]),
        ("GOOGLE", ["8.8.8.8", "8.8.4.4", "2001:4860:4860::8888", "2001:4860:4860::8844"]),
        ("Quad9", ["9.9.9.9", "149.112.112.112", "2606:4700:4700::1001"]),
        ("unknown", ["1.1.1.1", "1.0.0.1", "2606:4700:4700::1111", "2606:4700:4700::1001"]),
        ("", ["1.1.1.1", "1.0.0.1", "2606:4700:4700::1111", "2606:4700:4700::1001"]),
    ],
)
def test_dns_provider_selection_and_fallback(provider, expected):
    assert IPCompleter.suggest_dns(provider) == expected


def test_all_dns_providers_match_individual_results():
    providers = IPCompleter.suggest_all_dns()
    assert [name for name, _ in providers] == ["Cloudflare", "Google", "Quad9"]
    for name, servers in providers:
        assert servers == IPCompleter.suggest_dns(name)
        assert all(ipaddress.ip_address(server) for server in servers)


def test_ports_and_peer_names():
    assert IPCompleter.suggest_ports() == [51820, 51821, 51822, 443, 8443, 8080]
    assert IPCompleter.suggest_peer_names() == [
        "Office Network", "Home Device", "Mobile Hotspot", "Backup Server",
        "Development Machine", "Production Server", "IoT Device", "Remote Worker",
    ]


@pytest.mark.parametrize(
    ("method", "expected"),
    [
        ("suggest_class_a", ["10.0.0.0/8", "172.16.0.0/12", "192.0.0.0/24", "198.18.0.0/15"]),
        ("suggest_class_b", ["172.16.0.0/12", "172.16.0.0/16", "172.16.0.0/24", "198.51.100.0/24"]),
        ("suggest_class_c", ["192.168.0.0/16", "192.168.1.0/24", "192.168.1.0/24", "198.51.100.0/24"]),
        ("suggest_common_subnets", ["192.168.1.0/24", "192.168.0.0/16", "10.0.0.0/8", "172.16.0.0/12", "10.0.0.0/24", "172.16.0.0/24", "192.168.100.0/24"]),
    ],
)
def test_subnet_catalogs(method, expected):
    entries = getattr(IPCompleter, method)()
    assert [network for network, _ in entries] == expected
    assert all(ipaddress.IPv4Network(network) and description for network, description in entries)


@pytest.mark.parametrize(
    ("subnet", "description"),
    [
        ("192.168.1.123/24", "254 hosts"),
        ("10.0.0.0/8", "16,777,214 hosts"),
        ("10.0.0.0/30", "2 hosts"),
        ("invalid", "Unknown"),
        ("10.0.0.1/33", "Unknown"),
        ("fd00::/64", "Unknown"),
    ],
)
def test_subnet_description(subnet, description):
    assert IPCompleter._get_subnet_description(subnet) == description


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        ([], ["203.0.113.1", "203.0.113.2", "203.0.113.3", "203.0.113.4", "203.0.113.5", "203.0.113.6", "203.0.113.7", "203.0.113.8", "203.0.113.9", "203.0.113.10"]),
        (["10.0.0", "-c", "2"], ["10.0.0.2", "10.0.0.3"]),
        (["invalid"], []),
        (["-c", "0"], []),
    ],
)
def test_ip_command_prints_requested_suggestions(runner, args, expected):
    result = runner.invoke(ip_command, args)
    assert result.exit_code == 0, result.output
    assert result.output.splitlines() == ["Suggested IP addresses:"] + [
        f"  {i}. {ip}" for i, ip in enumerate(expected, 1)
    ]


def test_ip_command_rejects_non_integer_count(runner):
    result = runner.invoke(ip_command, ["--count", "many"])
    assert result.exit_code == 2
    assert "not a valid integer" in result.output


def test_subnet_callback_prints_common_ranges(capsys):
    subnet_command.callback("", "C")
    assert capsys.readouterr().out.splitlines() == [
        "Common subnet ranges:",
        "  192.168.1.0/24 - Class C - 254 hosts",
        "  192.168.0.0/16 - Class C - 65534 hosts",
        "  10.0.0.0/8 - Class A - 16M hosts",
        "  172.16.0.0/12 - Class B - 1M hosts",
    ]


@pytest.mark.parametrize("network", ["invalid", "10.0.0.0/33", "fd00::/64"])
def test_subnet_callback_reports_invalid_network(capsys, network):
    subnet_command.callback(network, "C")
    assert capsys.readouterr().out == "Invalid network format. Use: 192.168.1.0/24\n"


@pytest.mark.parametrize("args", [[], ["--class", "A"], ["-t", "B"]])
def test_subnet_command_accepts_default_class(runner, args):
    result = runner.invoke(subnet_command, args)
    assert result.exit_code == 0, repr(result.exception)
    assert "Common subnet ranges:" in result.output


def test_subnet_command_rejects_invalid_class(runner):
    result = runner.invoke(subnet_command, ["--class", "D"])
    assert result.exit_code == 2
    assert "Invalid value" in result.output


@pytest.mark.parametrize("network", ["192.168.1.42", "192.168.1.42/24"])
def test_subnet_callback_prints_actual_networks(capsys, network):
    subnet_command.callback(network, "C")
    output = capsys.readouterr().out
    assert output.splitlines() == ["Subnet suggestions:"] + [
        f"  {i}. {subnet}" for i, subnet in enumerate([
            "192.168.1.0/24", "192.168.1.0/26", "192.168.1.64/26",
            "192.168.1.128/26", "192.168.1.192/26", "192.168.1.0/28",
            "192.168.1.16/28", "192.168.1.32/28", "192.168.1.48/28", "192.168.1.64/28",
        ], 1)
    ]


@pytest.mark.parametrize(
    ("network", "expected"),
    [
        ("10.0.0.0/8", [f"10.0.{i}.0/24" for i in range(10)]),
        ("192.168.1.128/25", [
            "192.168.1.128/26", "192.168.1.192/26", "192.168.1.128/28",
            "192.168.1.144/28", "192.168.1.160/28", "192.168.1.176/28",
            "192.168.1.192/28", "192.168.1.208/28", "192.168.1.224/28", "192.168.1.240/28",
        ]),
        ("192.168.1.4/30", ["192.168.1.4/30"]),
        ("192.168.1.4/31", ["192.168.1.4/31"]),
        ("192.168.1.4/32", ["192.168.1.4/32"]),
    ],
)
def test_subnet_command_enumerates_bounded_subnets(runner, network, expected):
    result = runner.invoke(subnet_command, [network, "--class", "C"])
    assert result.exit_code == 0, repr(result.exception)
    assert result.output.splitlines() == ["Subnet suggestions:"] + [
        f"  {i}. {subnet}" for i, subnet in enumerate(expected, 1)
    ]


@pytest.mark.parametrize(
    ("provider", "servers"),
    [
        ("cloudflare", ["1.1.1.1", "1.0.0.1", "2606:4700:4700::1111", "2606:4700:4700::1001"]),
        ("google", ["8.8.8.8", "8.8.4.4", "2001:4860:4860::8888", "2001:4860:4860::8844"]),
        ("cloud", ["9.9.9.9", "149.112.112.112"]),
    ],
)
def test_dns_command_prints_provider_servers(runner, provider, servers):
    result = runner.invoke(dns_command, ["--provider", provider])
    assert result.exit_code == 0
    assert result.output.splitlines() == [f"Suggested DNS ({provider}):"] + [f"  {server}" for server in servers]


def test_dns_command_defaults_to_cloudflare_and_rejects_unknown_provider(runner):
    assert runner.invoke(dns_command, []).output.startswith("Suggested DNS (cloudflare):\n  1.1.1.1\n")
    result = runner.invoke(dns_command, ["-p", "unknown"])
    assert result.exit_code == 2
    assert "Invalid value" in result.output


def test_port_command_without_range_separator(runner):
    result = runner.invoke(port_command, ["--range", "none"])
    assert result.exit_code == 0
    assert result.output.splitlines() == ["Common WireGuard ports:", "  51820", "  51821", "  51822", "  443", "  8443", "  8080"]


@pytest.mark.parametrize(("args", "expected"), [
    ([], list(range(51820, 51830))),
    (["--range", "10-12"], [10, 11, 12]),
    (["-r", "10-100"], list(range(10, 20))),
    (["-r", "12-10"], []),
])
def test_port_command_prints_ports_from_range(runner, args, expected):
    result = runner.invoke(port_command, args)
    assert result.exit_code == 0, repr(result.exception)
    assert result.output.split("\nFrom range:\n")[1].splitlines() == [f"  {port}" for port in expected]


@pytest.mark.parametrize("port_range", ["a-b", "1-2-3"])
def test_port_command_reports_malformed_range_as_error(runner, port_range):
    result = runner.invoke(port_command, ["--range", port_range])
    assert result.exit_code == 1
    assert isinstance(result.exception, ValueError)


def test_peer_command_prints_names_and_endpoints(runner):
    result = runner.invoke(peer_command, ["--server-port", "12345", "custom name"])
    assert result.exit_code == 0
    assert "  1. Office Network\n" in result.output
    assert "  8. Remote Worker\n" in result.output
    assert "Suggested endpoints (based on port 12345):\n" in result.output
    assert result.output.endswith("  192.168.1.100\n  192.168.1.101\n  192.168.1.102\n  203.0.113.50\n  10.0.0.50\n  172.16.0.100\n")


def test_peer_command_rejects_non_integer_port(runner):
    result = runner.invoke(peer_command, ["--server-port", "invalid"])
    assert result.exit_code == 2
    assert "not a valid integer" in result.output


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        (["ip", "--prefix", "10.0.0", "--count", "1"], "10.0.0.2"),
        (["subnet", "--class", "A"], "10.0.0.0/8"),
        (["subnet", "--class", "B"], "172.16.0.0/16"),
        (["subnet", "--class", "C"], "192.168.0.0/16"),
        (["subnet"], "192.168.100.0/24"),
        (["dns"], "Cloudflare DNS:"),
        (["port"], "51820"),
        (["peer"], "Office Network"),
    ],
)
def test_main_cli_completer_commands(runner, args, expected):
    result = runner.invoke(cli, ["completers", *args])
    assert result.exit_code == 0, repr(result.exception)
    assert expected in result.output


def test_main_cli_provider_specific_dns(runner):
    result = runner.invoke(cli, ["completers", "dns", "--provider", "google"])
    assert result.exit_code == 0, repr(result.exception)
    assert "8.8.8.8" in result.output
