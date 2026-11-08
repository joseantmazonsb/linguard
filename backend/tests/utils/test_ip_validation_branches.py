"""Remaining branches of app.utils.ip_validation (subnet/hostname/email/token).

The earlier suite covers the happy paths; this one targets the validation
branches that decide whether a peer/server address may be saved: subnet
membership rules, server subnet conflicts, hostname/email/token shape and the
private/reserved classifiers.
"""
import base64

import pytest

from app.utils import ip_validation as ipv


class TestValidatePeerSubnet:
    @pytest.mark.parametrize(
        ("peer_ip", "server_ip"),
        [
            (None, "10.0.0.0/24"),
            ("", "10.0.0.0/24"),
            ("   ", "10.0.0.0/24"),
        ],
    )
    def test_should_accept_empty_peer_ip(self, peer_ip, server_ip):
        assert ipv.is_ip_in_subnet(peer_ip, server_ip) == (True, None)

    @pytest.mark.parametrize("server_ip", [None, "", "  "])
    def test_should_reject_missing_server_ip(self, server_ip):
        ok, message = ipv.is_ip_in_subnet("10.0.0.5", server_ip)

        assert ok is False
        assert "Server IP is required" in message

    def test_should_accept_peer_inside_server_subnet(self):
        assert ipv.is_ip_in_subnet("10.0.0.5", "10.0.0.0/24") == (True, None)

    def test_should_reject_peer_outside_server_subnet(self):
        ok, message = ipv.is_ip_in_subnet("10.0.1.5", "10.0.0.0/24")

        assert ok is False
        assert "not within server subnet" in message

    def test_should_compare_plain_ipv4_addresses_within_slash_24(self):
        assert ipv.is_ip_in_subnet("192.168.1.10", "192.168.1.1") == (True, None)

    def test_should_reject_plain_ipv4_addresses_in_different_slash_24(self):
        ok, message = ipv.is_ip_in_subnet("192.168.2.10", "192.168.1.1")

        assert ok is False
        assert "same /24 subnet" in message

    def test_should_compare_plain_ipv6_addresses_within_slash_64(self):
        assert ipv.is_ip_in_subnet("fd00::2", "fd00::1") == (True, None)

    def test_should_reject_plain_ipv6_addresses_in_different_slash_64(self):
        ok, message = ipv.is_ip_in_subnet("fd00:1::2", "fd00::1")

        assert ok is False
        assert "same /64 subnet" in message

    def test_should_check_server_inside_peer_cidr(self):
        assert ipv.is_ip_in_subnet("10.0.0.0/24", "10.0.0.1") == (True, None)

    def test_should_reject_server_outside_peer_cidr(self):
        ok, message = ipv.is_ip_in_subnet("10.0.0.0/24", "10.0.9.1")

        assert ok is False
        assert "not within peer subnet" in message

    def test_should_report_parse_errors(self):
        ok, message = ipv.is_ip_in_subnet("not-an-ip", "10.0.0.0/24")

        assert ok is False
        assert message.startswith("Error validating subnet")


class TestValidateServerSubnetConflict:
    def test_should_accept_missing_new_ip(self):
        assert ipv.check_server_ip_subnet_conflicts(None, ["10.0.0.0/24"]) == (True, None)

    @pytest.mark.parametrize("new_ip", ["", "   "])
    def test_should_reject_blank_new_ip(self, new_ip):
        ok, message = ipv.check_server_ip_subnet_conflicts(new_ip, ["10.0.0.0/24"])

        assert ok is False
        assert message == "New server IP is required"

    def test_should_accept_when_there_are_no_existing_ips(self):
        assert ipv.check_server_ip_subnet_conflicts("10.0.0.0/24", None) == (True, None)
        assert ipv.check_server_ip_subnet_conflicts("10.0.0.0/24", []) == (True, None)

    def test_should_accept_disjoint_subnets(self):
        assert ipv.check_server_ip_subnet_conflicts(
            "10.1.0.0/24", ["10.0.0.0/24"]
        ) == (True, None)

    def test_should_flag_new_host_inside_existing_subnet(self):
        ok, message = ipv.check_server_ip_subnet_conflicts(
            "10.0.0.5/24", ["10.0.0.0/24"]
        )

        assert ok is False
        assert "conflicts with existing server" in message

    def test_should_flag_existing_host_inside_new_subnet(self):
        ok, message = ipv.check_server_ip_subnet_conflicts(
            "10.0.0.0/16", ["10.0.5.0/24"]
        )

        assert ok is False
        assert "conflicts with new server" in message

    def test_should_flag_exact_duplicate(self):
        ok, message = ipv.check_server_ip_subnet_conflicts(
            "10.0.0.0/24", ["10.0.0.0/24"]
        )

        assert ok is False
        assert "already in use" in message

    def test_should_accept_named_tuples_and_skip_blank_entries(self):
        ok, _ = ipv.check_server_ip_subnet_conflicts(
            "10.9.0.0/24", [("", "legacy"), ("10.0.0.0/24", "wg0")]
        )

        assert ok is True

    def test_should_name_the_conflicting_server(self):
        ok, message = ipv.check_server_ip_subnet_conflicts(
            "10.0.5.0/24", [("10.0.0.0/16", "office")]
        )

        assert ok is False
        assert "office" in message

    def test_should_report_parse_errors(self):
        ok, message = ipv.check_server_ip_subnet_conflicts("bogus/24", ["10.0.0.0/24"])

        assert ok is False
        assert message.startswith("Error validating subnet conflicts")


class TestHostname:
    @pytest.mark.parametrize(
        "hostname",
        ["vpn.example.com", "localhost", "wg-1.internal", "a"],
    )
    def test_should_accept_valid_hostnames(self, hostname):
        assert ipv.is_valid_hostname(hostname) == (True, None)

    def test_should_reject_empty_part(self):
        ok, message = ipv.is_valid_hostname("vpn..example.com")

        assert ok is False
        assert "empty part" in message

    def test_should_reject_trailing_dot(self):
        ok, message = ipv.is_valid_hostname("vpn.example.com.")

        assert ok is False
        assert "empty part" in message

    def test_should_reject_part_longer_than_63_chars(self):
        ok, message = ipv.is_valid_hostname("a" * 64 + ".com")

        assert ok is False
        assert "too long" in message

    def test_should_reject_leading_hyphen(self):
        ok, message = ipv.is_valid_hostname("-vpn.example.com")

        assert ok is False
        assert "hyphens not allowed" in message

    def test_should_reject_trailing_hyphen(self):
        ok, message = ipv.is_valid_hostname("vpn-.example.com")

        assert ok is False
        assert "hyphens not allowed" in message


class TestEmail:
    def test_should_reject_consecutive_dots(self):
        ok, message = ipv.is_valid_email("john..doe@example.com")

        assert ok is False
        assert "consecutive dots" in message

    @pytest.mark.parametrize("email", ["john@", "@example.com", "no-at-sign", "a@b.c"])
    def test_should_reject_incomplete_addresses(self, email):
        ok, message = ipv.is_valid_email(email)

        assert ok is False
        assert message == "Invalid email format"

    def test_should_accept_localhost_alias(self):
        assert ipv.is_valid_email("localhost") == (True, None)

    def test_should_accept_regular_address(self):
        assert ipv.is_valid_email("ops@example.com") == (True, None)


class TestToken:
    def test_should_reject_empty_token(self):
        assert ipv.is_valid_token("   ") == (False, "Token cannot be empty")
        assert ipv.is_valid_token(None) == (False, "Token cannot be empty")

    def test_should_reject_jwt_with_wrong_part_count(self):
        ok, message = ipv.is_valid_token("aaa.bbb")

        assert ok is False
        assert "Invalid JWT token format" in message

    def test_should_reject_jwt_with_empty_part(self):
        part = base64.b64encode(b"payload").decode()

        ok, message = ipv.is_valid_token(f"{part}..{part}")

        assert ok is False
        assert "empty part" in message

    def test_should_reject_jwt_with_non_base64_part(self):
        ok, message = ipv.is_valid_token("aaa.bb*b.ccc")

        assert ok is False
        assert "base64" in message

    def test_should_accept_valid_base64_jwt(self):
        part = base64.b64encode(b'{"alg":"HS256"}').decode()

        assert ipv.is_valid_token(f"{part}.{part}.{part}") == (True, None)


class TestNormalizeAndCidr:
    def test_should_return_none_for_blank_input(self):
        assert ipv.parse_ip_address(None) is None
        assert ipv.parse_ip_address("  ") is None

    def test_should_keep_valid_ipv4_and_ipv6(self):
        assert ipv.parse_ip_address(" 10.0.0.1 ") == "10.0.0.1"
        assert ipv.parse_ip_address("fd00::1/64") == "fd00::1/64"

    def test_should_return_none_for_invalid_ip(self):
        assert ipv.parse_ip_address("999.999.999.999") is None

    def test_should_detect_ip_in_cidr(self):
        assert ipv.is_ip_in_cidr("10.0.0.5", "10.0.0.0/24") is True
        assert ipv.is_ip_in_cidr("10.0.1.5", "10.0.0.0/24") is False

    def test_should_return_false_for_invalid_cidr_inputs(self):
        assert ipv.is_ip_in_cidr("", "10.0.0.0/24") is False
        assert ipv.is_ip_in_cidr("10.0.0.5", "not-a-cidr") is False


class TestPrivateAndReserved:
    def test_should_reject_empty_ip(self):
        assert ipv.is_private_ip("") == (False, "IP address cannot be empty")
        assert ipv.is_reserved_ip("") == (False, "IP address cannot be empty")

    @pytest.mark.parametrize("ip", ["10.0.0.1", "172.16.5.4", "192.168.1.1"])
    def test_should_accept_rfc1918_addresses(self, ip):
        assert ipv.is_private_ip(ip) == (True, None)

    def test_should_treat_loopback_as_private(self):
        # Python's ipaddress reports 127.0.0.0/8 as private; document that the
        # helper follows the stdlib definition rather than only RFC 1918.
        assert ipv.is_private_ip("127.0.0.1") == (True, None)

    def test_should_reject_public_ipv4(self):
        ok, message = ipv.is_private_ip("8.8.8.8")

        assert ok is False
        assert "public IP" in message

    def test_should_accept_ipv6_unique_local_and_link_local(self):
        assert ipv.is_private_ip("fd00::1") == (True, None)
        assert ipv.is_private_ip("fe80::1") == (True, None)

    def test_should_reject_public_ipv6(self):
        ok, message = ipv.is_private_ip("2001:4860:4860::8888")

        assert ok is False
        assert "public IP" in message

    def test_should_report_invalid_ip_for_private_check(self):
        ok, message = ipv.is_private_ip("nope")

        assert ok is False
        assert message.startswith("Error") or "Invalid" in message

    @pytest.mark.parametrize(
        "ip",
        ["127.0.0.1", "0.0.0.0", "224.0.0.1", "10.0.0.1", "169.254.1.1", "fe80::1"],
    )
    def test_should_flag_reserved_ranges(self, ip):
        assert ipv.is_reserved_ip(ip) == (True, None)

    def test_should_not_treat_ipv6_ula_as_reserved(self):
        # fd00::/8 is private-but-not-reserved; the reserved classifier only
        # reports stdlib "reserved" ranges.
        ok, message = ipv.is_reserved_ip("fd00::1")

        assert ok is False
        assert "not a reserved IP" in message

    def test_should_reject_public_address_as_reserved(self):
        ok, message = ipv.is_reserved_ip("1.1.1.1")

        assert ok is False
        assert "not a reserved IP" in message

    def test_should_report_invalid_ip_for_reserved_check(self):
        ok, message = ipv.is_reserved_ip("nope")

        assert ok is False
        assert message.startswith("Invalid IP address")
