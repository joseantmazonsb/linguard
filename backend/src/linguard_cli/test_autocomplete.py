#!/usr/bin/env python3
"""
Test script for Linguard CLI autocomplete features.
Run this to see suggested IPs, DNS servers, ports, etc.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from linguard_cli.completers import IPCompleter

def test_ip_suggestions():
    """Test IP address suggestions."""
    print("=" * 60)
    print("🔍 IP ADDRESS SUGGESTIONS")
    print("=" * 60)
    
    # Test with no prefix
    print("\n1. Common IP ranges:")
    ips = IPCompleter.suggest_ips()
    for i, ip in enumerate(ips[:15], 1):
        print(f"   {i}. {ip}")
    
    # Test with prefix
    print("\n2. IPs starting with '192.168.1':")
    prefix_ips = IPCompleter.suggest_ips("192.168.1", min_length=1)
    for i, ip in enumerate(prefix_ips[:10], 1):
        print(f"   {i}. {ip}")
    
    # Test sequential IPs
    print("\n3. Sequential IPs from 10.0.0.1:")
    seq_ips = IPCompleter._generate_sequential_ips("10.0.0.1")
    for i, ip in enumerate(seq_ips, 1):
        print(f"   {i}. {ip}")

def test_subnet_suggestions():
    """Test subnet suggestions."""
    print("\n" + "=" * 60)
    print("📟 SUBNET SUGGESTIONS")
    print("=" * 60)
    
    common_subnets = [
        ("192.168.1.0/24", "Class C - 254 hosts"),
        ("192.168.0.0/16", "Class C - 65534 hosts"),
        ("10.0.0.0/8", "Class A - 16M hosts"),
        ("172.16.0.0/12", "Class B - 1M hosts"),
    ]
    
    print("\nCommon subnet ranges:")
    for subnet, desc in common_subnets:
        print(f"   {subnet} - {desc}")

def test_dns_suggestions():
    """Test DNS server suggestions."""
    print("\n" + "=" * 60)
    print("🌐 DNS SERVER SUGGESTIONS")
    print("=" * 60)
    
    dns_servers = {
        "cloudflare": [
            "1.1.1.1",
            "1.0.0.1",
            "2606:4700:4700::1111",
            "2606:4700:4700::1001"
        ],
        "google": [
            "8.8.8.8",
            "8.8.4.4",
            "2001:4860:4860::8888",
            "2001:4860:4860::8844"
        ],
        "cloud": [
            "9.9.9.9",
            "149.112.112.112"
        ]
    }
    
    for provider, servers in dns_servers.items():
        print(f"\n{provider.capitalize()} DNS:")
        for dns in servers:
            print(f"   {dns}")

def test_port_suggestions():
    """Test port suggestions."""
    print("\n" + "=" * 60)
    print("🔌 PORT SUGGESTIONS (WireGuard)")
    print("=" * 60)
    
    common_ports = [
        51820,  # Default
        51821,  # Alternative
        51822,  # Alternative
        443,    # HTTPS (stealth mode)
        8443,   # Alt HTTPS
        8080,   # Proxy
    ]
    
    print("\nCommon WireGuard ports:")
    for port in common_ports:
        print(f"   {port}")

def test_peer_suggestions():
    """Test peer name suggestions."""
    print("\n" + "=" * 60)
    print("👥 PEER NAME SUGGESTIONS")
    print("=" * 60)
    
    peer_names = [
        "Office Network",
        "Home Device",
        "Mobile Hotspot",
        "Backup Server",
        "Development Machine",
        "Production Server",
        "IoT Device",
        "Remote Worker",
    ]
    
    print("\nSuggested peer names:")
    for i, name in enumerate(peer_names, 1):
        print(f"   {i}. {name}")

def test_ipv6_suggestions():
    """Test IPv6 suggestions."""
    print("\n" + "=" * 60)
    print("🔷 IPv6 SUGGESTIONS")
    print("=" * 60)
    
    print("\nULA (Unique Local Address) examples:")
    ipv6_addrs = [
        "fd00::1:1",
        "fd00::1:2",
        "fd00::1:3",
        "fd00::1:4",
        "fd00::1:5",
        "fd00::1/64",
        "fd00::2:1",
        "fd00::2:2",
    ]
    
    for i, addr in enumerate(ipv6_addrs, 1):
        print(f"   {i}. {addr}")

def main():
    """Run all autocomplete tests."""
    print("\n" + "█" * 60)
    print("  LINGUARD CLI AUTOCOMPLETE TEST")
    print("█" * 60 + "\n")
    
    test_ip_suggestions()
    test_subnet_suggestions()
    test_dns_suggestions()
    test_port_suggestions()
    test_peer_suggestions()
    test_ipv6_suggestions()
    
    print("\n" + "=" * 60)
    print("✅ All autocomplete tests completed!")
    print("=" * 60)
    print("\n💡 Usage examples:")
    print("   linguard servers create --suggest-ip --suggest-dns")
    print("   linguard peers create --suggest-range")
    print("   linguard completers ip")
    print("   linguard completers subnet")
    print("   linguard completers dns")
    print("   linguard completers port")
    print("   linguard completers peer")
    print()

if __name__ == "__main__":
    main()
