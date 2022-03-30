using System;
using System.Collections.Generic;
using Core.Test.Mocks;
using Core.Test.Stubs;
using FluentAssertions;
using Linguard.Core;
using Linguard.Core.Configuration;
using Linguard.Core.Models.Wireguard;
using Microsoft.Extensions.Logging;
using Xunit;
using YamlConfigurationSerializerMock = Yaml.Test.Mocks.YamlConfigurationSerializerMock;

namespace Yaml.Test; 

public class YamlConfigurationSerializerShould {

    #region Yaml string

    const string yaml = @"Modules:
- !Logging
  Level: Debug
  DateTimeFormat: yyyy-MM-dd
- !Traffic
  Enabled: false
  StorageDriver:
    Name: Stub driver
    Description: This is a stub driver
    CollectionInterval: 01:00:00
    AdditionalOptions:
      Fake: Option
- !Wireguard
  Interfaces:
  - Gateway: eth0
    Port: 0
    Auto: false
    Clients:
    - AllowedIPs:
      - 1.1.1.0/24
      - 1.1.2.0/24
      Nat: false
      PrimaryDns: ''
      SecondaryDns: ''
      Endpoint: vpn.example.com
      PublicKey: 00000000-0000-0000-0000-000000000000
      PrivateKey: 
      IPv4Address: 1.1.1.2/30
      IPv6Address: ''
      Name: peer1
      Description: 
    - AllowedIPs:
      - 1.1.1.0/24
      - 1.1.2.0/24
      Nat: false
      PrimaryDns: ''
      SecondaryDns: ''
      Endpoint: 192.168.0.1
      PublicKey: 00000000-0000-0000-0000-000000000001
      PrivateKey: 
      IPv4Address: 1.1.1.3/30
      IPv6Address: ''
      Name: peer2
      Description: 
    - AllowedIPs: 
      Nat: false
      PrimaryDns: ''
      SecondaryDns: ''
      Endpoint: ''
      PublicKey: 00000000-0000-0000-0000-000000000002
      PrivateKey: 
      IPv4Address: 1.1.1.4/30
      IPv6Address: ''
      Name: peer3
      Description: 
    OnUp:
    - iptables fake rule 1
    - iptables fake rule 2
    OnDown: 
    PrimaryDns: ''
    SecondaryDns: ''
    Endpoint: ''
    PublicKey: ifacePubkey
    PrivateKey: 
    IPv4Address: 1.1.1.1/24
    IPv6Address: ''
    Name: wg1
    Description: 
  IptablesBin: iptables
  WireguardBin: wg
  WireguardQuickBin: wg-quick
  PrimaryDns: ''
  SecondaryDns: ''
  Endpoint: ''";
    #endregion

    [Fact]
    public void Deserialize() {
        var serializer = YamlConfigurationSerializerMock.Instance;
        var config = serializer.Deserialize<IConfiguration>(yaml);
        config.Modules.Should().ContainItemsAssignableTo<ILoggingConfiguration>();
        config.Modules.Should().ContainItemsAssignableTo<IWireguardConfiguration>();
        config.Modules.Should().ContainItemsAssignableTo<ITrafficConfiguration>();
    }
    
    [Fact]
    public void Serialize() {
        var config = new ConfigurationBase {
            Modules = {
                new LoggingConfiguration {
                    Level = LogLevel.Debug,
                    DateTimeFormat = "yyyy-MM-dd"
                },
                new TrafficConfiguration {
                    Enabled = false,
                    StorageDriver = new TrafficStorageDriverStub()
                },
                new WireguardConfiguration {
                    Interfaces = new HashSet<Interface> {new() {
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
                    }},
                    IptablesBin = "iptables",
                    WireguardBin = "wg",
                    WireguardQuickBin = "wg-quick"
                }
            }
        };
        var serializer = YamlConfigurationSerializerMock.Instance;
        var output = serializer.Serialize(config);
        output.Trim().Should().Be(yaml.Trim());
    }

    [Fact]
    public void SerializeEmpty() {
        var yaml = @"Modules: []";
        var serializer = YamlConfigurationSerializerMock.Instance;
        var output = serializer.Serialize(new ConfigurationBase());
        output.Trim().Should().Be(yaml);
    }
    
    [Fact]
    public void DeserializeEmpty() {
        var yaml = @"Modules: []";
        var serializer = YamlConfigurationSerializerMock.Instance;
        var output = serializer.Deserialize<IConfiguration>(yaml);
        var config = new ConfigurationBase();
        output.Should().Be(config);
    }
}