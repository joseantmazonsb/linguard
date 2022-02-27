using System;
using FluentAssertions;
using Linguard.Core;
using Linguard.Core.Models.Wireguard;
using Linguard.Core.Utils.Wireguard;
using Xunit;

namespace Core.Test; 

public class ClientShould {
    [Fact]
    public void CreateValidWireguardConfig() {
        
        #region Expected config

        const string expected = @"[Interface]
PrivateKey = f0c4e3be-11b6-4f80-8eb3-27f63e488253
Address = 1.1.1.2/30, 7d1d:393:2abb:ffbf:58e5:9355:e7d3:4378/64
DNS = 8.8.8.8

[Peer]
PublicKey = 0514b8fe-951f-4bf1-829c-0d327da6e949
AllowedIPs = 1.1.2.0/24
Endpoint = vpn.example.com
PersistentKeepalive = 25";

        #endregion
        
        var peer = new Client {
            Endpoint = new Uri("vpn.example.com", UriKind.RelativeOrAbsolute),
            Name = "peer1",
            Nat = true,
            IPv4Address = IPAddressCidr.Parse("1.1.1.2/30"),
            IPv6Address = IPAddressCidr.Parse("7d1d:393:2abb:ffbf:58e5:9355:e7d3:4378/64"),
            PublicKey = "0514b8fe-951f-4bf1-829c-0d327da6e949",
            PrivateKey = "f0c4e3be-11b6-4f80-8eb3-27f63e488253",
            AllowedIPs = new[] { IPAddressCidr.Parse("1.1.2.0/24") },
            PrimaryDns = new Uri("8.8.8.8", UriKind.RelativeOrAbsolute)
        };
        var output = WireguardUtils.GenerateWireguardConfiguration(peer);
        output.Should().Be(expected);
    }
    
    [Fact]
    public void CreateAnotherValidWireguardConfig() {
        
        #region Expected config

        const string expected = @"[Interface]
PrivateKey = 558afbed-c606-4ad4-b70a-eb48af4004bd
Address = 1.1.1.2/30, 9f87:8784:c972:21f4:62b6:34a0:80e4:43df/64
DNS = dns1.example.com, dns2.example.com

[Peer]
PublicKey = 4a58a41a-8ed5-4c7d-b2b6-0b9652eec346
AllowedIPs = 1.1.1.0/24, 9f87:8784:c972:21f4:62b6:34a0:80e4:43de/64
Endpoint = vpn2.example.com";

        #endregion

        var peer = new Client {
            Endpoint = new Uri("vpn2.example.com", UriKind.RelativeOrAbsolute),
            Name = "peer2",
            IPv4Address = IPAddressCidr.Parse("1.1.1.2/30"),
            IPv6Address = IPAddressCidr.Parse("9f87:8784:c972:21f4:62b6:34a0:80e4:43df/64"),
            PublicKey = "4a58a41a-8ed5-4c7d-b2b6-0b9652eec346",
            PrivateKey = "558afbed-c606-4ad4-b70a-eb48af4004bd",
            AllowedIPs = new[] {
                IPAddressCidr.Parse("1.1.1.0/24"),
                IPAddressCidr.Parse("9f87:8784:c972:21f4:62b6:34a0:80e4:43de/64")
            },
            PrimaryDns = new Uri("dns1.example.com", UriKind.RelativeOrAbsolute),
            SecondaryDns = new Uri("dns2.example.com", UriKind.RelativeOrAbsolute),
        };
        var output = WireguardUtils.GenerateWireguardConfiguration(peer);
        output.Trim().Should().Be(expected.Trim());
    }
}