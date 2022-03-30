using System;
using System.Collections.Generic;
using System.Linq;
using Bogus;
using Core.Test.Mocks;
using FluentAssertions;
using Linguard.Core;
using Linguard.Core.Configuration;
using Linguard.Core.Managers;
using Linguard.Core.Models.Wireguard;
using Linguard.Core.OS;
using Linguard.Core.Services;
using Linguard.Core.Utils.Wireguard;
using Xunit;

namespace Core.Test; 

public class WireguardConfigParserShould {
    private static readonly IConfigurationManager Manager = new DefaultConfigurationManager().Object;
    private static readonly ISystemWrapper System = new SystemMock().Object;
    private static readonly Faker Faker = new ();
    private static readonly IWireguardService WireguardService = new WireguardServiceMock(Manager, System, Faker).Object;
    private static readonly IWireguardConfigParser Parser = new WireguardConfigParser(Manager, WireguardService, Faker);
    private IWireguardConfiguration Configuration => Manager.Configuration.GetModule<IWireguardConfiguration>()!;
    
    public WireguardConfigParserShould() {
        Configuration.Interfaces.Add(new Interface {
            Name = "wg0",
            PublicKey = "server-pubkey",
            PrivateKey = "server-privkey",
            IPv4Address = IPAddressCidr.Parse("10.0.0.1", 24),
            Clients = new HashSet<Client> {
                new() {
                    Name = "Michael Scott",
                    Description = "Scranton branch's manager",
                    IPv4Address = IPAddressCidr.Parse("10.0.0.2", 24),
                    PrimaryDns = new Uri("1.1.1.1", UriKind.RelativeOrAbsolute),
                    PublicKey = "client-pubkey",
                    PrivateKey = "client-privkey",
                    AllowedIPs = new HashSet<IPAddressCidr> {
                        IPAddressCidr.Parse("0.0.0.0", 0),
                        IPAddressCidr.Parse("::/0")
                    }
                }
            },
            OnUp = new HashSet<Rule> {
                "iptables -A FORWARD -i wg0 -j ACCEPT",
                "iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE"
            },
            OnDown = new HashSet<Rule> {
                "iptables -D FORWARD -i wg0 -j ACCEPT",
                "iptables -t nat -D POSTROUTING -o eth0 -j MASQUERADE"
            }
        });
    }

    public void ParseInterface() {
        var iface = Configuration.Interfaces.First();
        var config = WireguardUtils.GenerateWireguardConfiguration(iface);
        var output = Parser.Parse<Interface>(config);
        output.Should().Be(iface);
    }
    
    [Fact]
    public void ParseClient() {
        const string config = @"[Interface]
Address = 10.0.0.2/24
PrivateKey = client-privkey
DNS = 1.1.1.1
#Name = Michael Scott
#Description = Scranton branch's manager

[Peer]
PublicKey = server-pubkey
Endpoint = vpn.example.com
AllowedIPs = 0.0.0.0/0, ::/0";

        var client = Parser.Parse<Client>(config);
        client.IPv4Address.Should().Be(IPAddressCidr.Parse("10.0.0.2/24"));
        client.PrivateKey.Should().Be("client-privkey");
        client.PublicKey.Should().NotBeEmpty();
        client.PrimaryDns.Should().Be(new Uri("1.1.1.1", UriKind.RelativeOrAbsolute));
        client.Name.Should().Be("Michael Scott");
        client.Description.Should().Be("Scranton branch's manager");
        client.Endpoint.Should().Be(new Uri("vpn.example.com", UriKind.RelativeOrAbsolute));
        client.AllowedIPs.Should().BeEquivalentTo(new HashSet<IPAddressCidr> {
            IPAddressCidr.Parse("0.0.0.0/0"),
            IPAddressCidr.Parse("::/0"),
        });
        Configuration.Interfaces
            .Single(i => i.Name == "wg0")
            .Clients
            .First()
            .Should().Be(client);
    }
}