using System;
using System.Collections.Generic;
using System.IO;
using System.Text.Json;
using Core.Test.Mocks;
using Core.Test.Stubs;
using FluentAssertions;
using Json.Test.Stubs;
using Linguard.Core;
using Linguard.Core.Configuration;
using Linguard.Core.Models.Wireguard;
using Xunit;

namespace Json.Test;

public class JsonSerializerShould {

    [Fact]
    public void SerializeTrafficConfiguration() {
        var config = new TrafficOptions {
            Enabled = false,
            StorageDriver = new TrafficStorageDriverStub()
        };
        const string expected = 
            "{\"Enabled\":false,\"StorageDriver\":{\"Name\":\"Stub driver\"," +
            "\"Description\":\"This is a stub driver\",\"CollectionInterval\":\"01:00:00\"," +
            "\"AdditionalOptions\":{\"Fake\":\"Option\"}}}";
        var options = new JsonSerializerOptionsBuilder(new SystemMock().Object, new PluginEngineMock().Object).Build();
        var output = JsonSerializer.Serialize(config, options);
        output.Trim().Should().Be(expected.Trim());
    }
    
    [Fact]
    public void SerializeConfiguration() {
        var json = File.ReadAllText("expected.json");
        var traffic = new TrafficOptions {
            Enabled = false,
            StorageDriver = new TrafficStorageDriverStub()
        };
        var auth = new AuthenticationOptions {
            DataSource = "auth.db"
        };
        var wireguard = new WireguardOptions {
            Interfaces = new HashSet<Interface> {
                new() {
                    PublicKey = "ifacePubkey",
                    Name = "wg1",
                    IPv4Address = IPAddressCidr.Parse("1.1.1.1/24"),
                    Gateway = new NetworkInterfaceMock("eth0").Object,
                    Clients = new HashSet<Client> {
                        new() {
                            Endpoint = new Uri("vpn.example.com", UriKind.RelativeOrAbsolute),
                            Name = "peer1",
                            IPv4Address = IPAddressCidr.Parse("1.1.1.2/30"),
                            AllowedIPs = new HashSet<IPAddressCidr> {
                                IPAddressCidr.Parse("1.1.1.0/24"), IPAddressCidr.Parse("1.1.2.0/24")
                            },
                            PublicKey = "00000000-0000-0000-0000-000000000000"
                        },
                        new() {
                            Endpoint = new Uri("192.168.0.1", UriKind.RelativeOrAbsolute),
                            Name = "peer2",
                            IPv4Address = IPAddressCidr.Parse("1.1.1.3/30"),
                            AllowedIPs = new HashSet<IPAddressCidr> {
                                IPAddressCidr.Parse("1.1.1.0/24"), IPAddressCidr.Parse("1.1.2.0/24")
                            },
                            PublicKey = "00000000-0000-0000-0000-000000000001"
                        },
                        new() {
                            Name = "peer3",
                            IPv4Address = IPAddressCidr.Parse("1.1.1.4/30"),
                            PublicKey = "00000000-0000-0000-0000-000000000002"
                        }
                    },
                    OnUp = new HashSet<Rule> {
                        "iptables fake rule 1", "iptables fake rule 2"
                    }
                }
            },
            IptablesBin = "iptables",
            WireguardBin = "wg",
            WireguardQuickBin = "wg-quick"
        };
        var plugins = new PluginOptions();
        var config = new ConfigurationBase {
            Traffic = traffic,
            Wireguard = wireguard,
            Plugins = plugins,
            Authentication = auth
        };
        var serializer = new JsonConfigurationSerializerStub(new SystemMock().Object, new PluginEngineMock().Object);
        var output = serializer.Serialize(config);
        output.Trim().Should().Be(json.Trim());
    }
    
    [Fact]
    public void DeserializeConfiguration() {
        var json = File.ReadAllText("expected.json");
        var traffic = new TrafficOptions {
            Enabled = false,
            StorageDriver = new TrafficStorageDriverStub()
        };
        var auth = new AuthenticationOptions {
            DataSource = "auth.db"
        };
        var wireguard = new WireguardOptions {
            Interfaces = new HashSet<Interface> {
                new() {
                    PublicKey = "ifacePubkey",
                    Name = "wg1",
                    IPv4Address = IPAddressCidr.Parse("1.1.1.1/24"),
                    Gateway = new NetworkInterfaceMock("eth0").Object,
                    Clients = new HashSet<Client> {
                        new() {
                            Endpoint = new Uri("vpn.example.com", UriKind.RelativeOrAbsolute),
                            Name = "peer1",
                            IPv4Address = IPAddressCidr.Parse("1.1.1.2/30"),
                            AllowedIPs = new HashSet<IPAddressCidr> {
                                IPAddressCidr.Parse("1.1.1.0/24"), IPAddressCidr.Parse("1.1.2.0/24")
                            },
                            PublicKey = "00000000-0000-0000-0000-000000000000"
                        },
                        new() {
                            Endpoint = new Uri("192.168.0.1", UriKind.RelativeOrAbsolute),
                            Name = "peer2",
                            IPv4Address = IPAddressCidr.Parse("1.1.1.3/30"),
                            AllowedIPs = new HashSet<IPAddressCidr> {
                                IPAddressCidr.Parse("1.1.1.0/24"), IPAddressCidr.Parse("1.1.2.0/24")
                            },
                            PublicKey = "00000000-0000-0000-0000-000000000001"
                        },
                        new() {
                            Name = "peer3",
                            IPv4Address = IPAddressCidr.Parse("1.1.1.4/30"),
                            PublicKey = "00000000-0000-0000-0000-000000000002"
                        }
                    },
                    OnUp = new HashSet<Rule> {
                        "iptables fake rule 1", "iptables fake rule 2"
                    }
                }
            },
            IptablesBin = "iptables",
            WireguardBin = "wg",
            WireguardQuickBin = "wg-quick"
        };
        var plugins = new PluginOptions();
        var config = new ConfigurationBase {
            Traffic = traffic,
            Wireguard = wireguard,
            Plugins = plugins,
            Authentication = auth
        };
        var serializer = new JsonConfigurationSerializerStub(new SystemMock().Object, new PluginEngineMock().Object);
        var output = serializer.Deserialize<IConfiguration>(json);
        output.Should().BeEquivalentTo(config);
    }
    
}