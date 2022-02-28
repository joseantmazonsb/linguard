using System;
using System.Linq;
using Core.Test.Mocks;
using FluentAssertions;
using Linguard.Core;
using Linguard.Core.Models.Wireguard;
using Linguard.Core.OS;
using Linguard.Core.Utils.Wireguard;
using Xunit;

namespace Core.Test;

public class InterfaceShould {
    private readonly ISystemWrapper _system = new SystemMock().Object;

    [Fact]
    public void CreateValidWireguardConfiguration() {
        
        #region Expected configuration
        const string expected = @"[Interface]
PrivateKey = 16116afc-3068-4ff5-88e0-0662ef57641a
Address = 1.1.1.1/24, 47cc:ec62:b8b4:d4c0:9c90:4c5c:1df5:a13f/64
ListenPort = 1337
PostUp = /usr/sbin/iptables -I FORWARD -i wg0 -j ACCEPT
PostUp = /usr/sbin/iptables -I FORWARD -o wg0 -j ACCEPT
PostUp = /usr/sbin/iptables -t nat -I POSTROUTING -o eth0 -j MASQUERADE
PostDown = /usr/sbin/iptables -D FORWARD -i wg0 -j ACCEPT
PostDown = /usr/sbin/iptables -D FORWARD -o wg0 -j ACCEPT
PostDown = /usr/sbin/iptables -t nat -D POSTROUTING -o eth0 -j MASQUERADE

[Peer]
PublicKey = 0514b8fe-951f-4bf1-829c-0d327da6e949
AllowedIPs = 1.1.1.2/32, 7d1d:393:2abb:ffbf:58e5:9355:e7d3:4378/128
[Peer]
PublicKey = 4a58a41a-8ed5-4c7d-b2b6-0b9652eec346
AllowedIPs = 1.1.1.2/32, 9f87:8784:c972:21f4:62b6:34a0:80e4:43df/128
";
        
        #endregion
        
        var iface = new Interface {
            Name = "wg0",
            Port = 1337,
            IPv4Address = IPAddressCidr.Parse("1.1.1.1/24"),
            IPv6Address = IPAddressCidr.Parse("47cc:ec62:b8b4:d4c0:9c90:4c5c:1df5:a13f/64"),
            PublicKey = "c892a52a-1fad-4564-af83-641744cd4dc3",
            PrivateKey = "16116afc-3068-4ff5-88e0-0662ef57641a",
            OnUp = new Rule[] {
                "/usr/sbin/iptables -I FORWARD -i wg0 -j ACCEPT",
                "/usr/sbin/iptables -I FORWARD -o wg0 -j ACCEPT",
                "/usr/sbin/iptables -t nat -I POSTROUTING -o eth0 -j MASQUERADE"
                },
            OnDown = new Rule[] {
                "/usr/sbin/iptables -D FORWARD -i wg0 -j ACCEPT",
                "/usr/sbin/iptables -D FORWARD -o wg0 -j ACCEPT",
                "/usr/sbin/iptables -t nat -D POSTROUTING -o eth0 -j MASQUERADE"
            },
            Gateway = _system.NetworkInterfaces.First(),
            Clients = new[] {
                new Client {
                    Endpoint = new Uri("vpn.example.com", UriKind.RelativeOrAbsolute),
                    Name = "peer1",
                    Nat = true,
                    IPv4Address = IPAddressCidr.Parse("1.1.1.2/30"),
                    IPv6Address = IPAddressCidr.Parse("7d1d:0393:2abb:ffbf:58e5:9355:e7d3:4378/64"),
                    PublicKey = "0514b8fe-951f-4bf1-829c-0d327da6e949",
                    PrivateKey = "f0c4e3be-11b6-4f80-8eb3-27f63e488253",
                    AllowedIPs = new[] { IPAddressCidr.Parse("1.1.2.0/24") },
                    PrimaryDns = new Uri("8.8.8.8", UriKind.RelativeOrAbsolute)
                },
                new Client {
                    Endpoint = new Uri("vpn2.example.com", UriKind.RelativeOrAbsolute),
                    Name = "peer2",
                    IPv4Address = IPAddressCidr.Parse("1.1.1.2/30"),
                    IPv6Address = IPAddressCidr.Parse("9f87:8784:c972:21f4:62b6:34a0:80e4:43df/64"),
                    PublicKey = "4a58a41a-8ed5-4c7d-b2b6-0b9652eec346",
                    PrivateKey = "558afbed-c606-4ad4-b70a-eb48af4004bd",
                    AllowedIPs = new[] { IPAddressCidr.Parse("1.1.1.0/24"), 
                        IPAddressCidr.Parse("9f87:8784:c972:21f4:62b6:34a0:80e4:43de/64")  },
                    PrimaryDns = new Uri("dns1.example.com", UriKind.RelativeOrAbsolute),
                    SecondaryDns = new Uri("dns2.example.com", UriKind.RelativeOrAbsolute),
                }
            }
        };
        var output = WireguardUtils.GenerateWireguardConfiguration(iface);
        output.Trim().Should().Be(expected.Trim());
    }
}