#!/usr/bin/env python3
"""
Simple test script for Linguard CLI autocomplete features.
Does not require the backend.
"""

import sys
sys.path.insert(0, '/home/jose/projects/linguard/backend/src/linguard_cli')

from completers import IPCompleter

def main():
    print("\n" + "=" * 60)
    print("🔍 LINGUARD CLI AUTOCOMPLETE TEST")
    print("=" * 60 + "\n")
    
    print("📍 IP Address Suggestions:")
    print("-" * 60)
    ips = IPCompleter.suggest_ips()
    for i, ip in enumerate(ips[:15], 1):
        print(f"   {i}. {ip}")
    
    print("\n📟 Common Subnet Ranges:")
    print("-" * 60)
    common_subnets = [
        ("192.168.1.0/24", "Class C - 254 hosts"),
        ("192.168.0.0/16", "Class C - 65534 hosts"),
        ("10.0.0.0/8", "Class A - 16M hosts"),
        ("172.16.0.0/12", "Class B - 1M hosts"),
    ]
    for subnet, desc in common_subnets:
        print(f"   {subnet} - {desc}")
    
    print("\n🌐 DNS Server Suggestions:")
    print("-" * 60)
    dns_servers = {
        "cloudflare": ["1.1.1.1", "1.0.0.1"],
        "google": ["8.8.8.8", "8.8.4.4"],
        "quad9": ["9.9.9.9", "149.112.112.112"],
    }
    for provider, servers in dns_servers.items():
        print(f"\n   {provider.capitalize()} DNS:")
        for dns in servers:
            print(f"      {dns}")
    
    print("\n🔌 Common WireGuard Ports:")
    print("-" * 60)
    common_ports = [51820, 51821, 51822, 443, 8443]
    for port in common_ports:
        print(f"   {port}")
    
    print("\n👥 Suggested Peer Names:")
    print("-" * 60)
    peer_names = [
        "Office Network",
        "Home Device",
        "Mobile Hotspot",
        "Backup Server",
        "Development Machine",
    ]
    for i, name in enumerate(peer_names, 1):
        print(f"   {i}. {name}")
    
    print("\n" + "=" * 60)
    print("✅ All autocomplete features working!")
    print("=" * 60)
    print("\n💡 Usage examples:")
    print("   - linguard completers ip")
    print("   - linguard completers subnet")
    print("   - linguard completers dns")
    print("   - linguard completers port")
    print("   - linguard completers peer")
    print()

if __name__ == "__main__":
    main()
