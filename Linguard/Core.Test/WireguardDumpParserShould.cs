using System;
using System.Collections.Generic;
using System.Linq;
using Core.Test.Mocks;
using FluentAssertions;
using Linguard.Core;
using Linguard.Core.Configuration;
using Linguard.Core.Managers;
using Linguard.Core.Models.Wireguard;
using Linguard.Core.Utils.Wireguard;
using Moq;
using Xunit;

namespace Core.Test; 

public class WireguardDumpParserShould {
    private static readonly Mock<IConfigurationManager> ConfigurationManagerMock = new DefaultConfigurationManager();
    private static IWireguardConfiguration Configuration 
        => ConfigurationManagerMock.Object.Configuration.GetModule<IWireguardConfiguration>()!;
    
    public WireguardDumpParserShould() {
        var iface = new Interface {
            Name = "wg1",
            Clients = new HashSet<Client> {
                new() {
                    Id = Guid.Parse("00000000-0000-0000-0000-000000000001"),
                    PublicKey = "fE/wdxzl0klVp/IR8UcaoGUMjqaWi3jAd7KzHKFS6Ds=",
                    AllowedIPs = new HashSet<IPAddressCidr>()
                },
                new() {
                    Id = Guid.Parse("00000000-0000-0000-0000-000000000002"),
                    PublicKey = "jUd41n3XYa3yXBzyBvWqlLhYgRef5RiBD7jwo70U+Rw=",
                    AllowedIPs = new HashSet<IPAddressCidr>()
                }
            },
            OnUp = new HashSet<Rule>(),
            OnDown = new HashSet<Rule>(),
            Gateway = new NetworkInterfaceMock("a").Object
        };
        Configuration.Interfaces.Add(iface);
        
    }

    [Fact]
    public void ExtractEmptyData() {
        const string sampleData =
            @"wg1     AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAEE=    /TOE4TKtAqVsePRVR+5AA43HkAK5DSntkOCO7nYq5xU=    13377   off
wg1     fE/wdxzl0klVp/IR8UcaoGUMjqaWi3jAd7KzHKFS6Ds=    (none)  (none)  (none)  0       0       0       off
wg1     jUd41n3XYa3yXBzyBvWqlLhYgRef5RiBD7jwo70U+Rw=    (none)  (none)  10.7.1.0/24     0       0       0       off";
        
        var data = 
            WireguardDumpParser.GetTrafficData(sampleData, Configuration.Interfaces.First());
        data.Should().HaveCount(3);
        var clients = data.Where(e => e.Peer is Client);
        clients.Should().HaveCount(2);
        var interfaces = data.Where(e => e.Peer is Interface);
        interfaces.Should().HaveCount(1);
        clients.Select(e => e.Peer).Should().BeEquivalentTo(Configuration.Interfaces.First().Clients);
        clients.First().ReceivedData.Should().Be(default);
        clients.First().SentData.Should().Be(default);
        clients.Last().ReceivedData.Should().Be(default);
        clients.Last().SentData.Should().Be(default);
        interfaces.Single().Peer.Should().Be(Configuration.Interfaces.First());
        interfaces.Single().ReceivedData.Bytes.Should().Be(clients.Sum(e => e.ReceivedData.Bytes));
        interfaces.Single().SentData.Bytes.Should().Be(clients.Sum(e => e.SentData.Bytes));
    }
    
    [Fact]
    public void ExtractDataFromSingleInterface() {
        const string sampleData =
            @"wg1	AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAEE=	/TOE4TKtAqVsePRVR+5AA43HkAK5DSntkOCO7nYq5xU=	51821	off
wg1	fE/wdxzl0klVp/IR8UcaoGUMjqaWi3jAd7KzHKFS6Ds=	(none)	172.19.0.8:51822	10.0.0.2/32	1617235493	3481633	33460136	off
wg1	jUd41n3XYa3yXBzyBvWqlLhYgRef5RiBD7jwo70U+Rw=	(none)	172.19.0.7:51823	10.0.0.3/32	1609974495	1403752	19462368	off";
        
        var data = 
            WireguardDumpParser.GetTrafficData(sampleData, Configuration.Interfaces.First());
        data.Should().HaveCount(3);
        var clients = data.Where(e => e.Peer is Client);
        clients.Should().HaveCount(2);
        var interfaces = data.Where(e => e.Peer is Interface);
        interfaces.Should().HaveCount(1);
        clients.Select(e => e.Peer).Should().BeEquivalentTo(Configuration.Interfaces.First().Clients);
        clients.First().ReceivedData.Bytes.Should().Be(3481633);
        clients.First().SentData.Bytes.Should().Be(33460136);
        clients.Last().ReceivedData.Bytes.Should().Be(1403752);
        clients.Last().SentData.Bytes.Should().Be(19462368);
        interfaces.Single().Peer.Should().Be(Configuration.Interfaces.First());
        interfaces.Single().ReceivedData.Bytes.Should().Be(clients.Sum(e => e.ReceivedData.Bytes));
        interfaces.Single().SentData.Bytes.Should().Be(clients.Sum(e => e.SentData.Bytes));
    }
    
    [Fact]
    public void GetLastHandshakeForPeers() {
        const string sampleData =
            @"wg1	AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAEE=	/TOE4TKtAqVsePRVR+5AA43HkAK5DSntkOCO7nYq5xU=	51821	off
wg1	fE/wdxzl0klVp/IR8UcaoGUMjqaWi3jAd7KzHKFS6Ds=	(none)	172.19.0.8:51822	10.0.0.2/32	1617235493	3481633	33460136	off
wg1	jUd41n3XYa3yXBzyBvWqlLhYgRef5RiBD7jwo70U+Rw=	(none)	172.19.0.7:51823	10.0.0.3/32	1609974495	1403752	19462368	off";

        WireguardDumpParser.GetLastHandshake(sampleData, new Client {
            PublicKey = "fE/wdxzl0klVp/IR8UcaoGUMjqaWi3jAd7KzHKFS6Ds="
        }).Ticks.Should().Be(1617235493);
        
        WireguardDumpParser.GetLastHandshake(sampleData, new Client {
            PublicKey = "jUd41n3XYa3yXBzyBvWqlLhYgRef5RiBD7jwo70U+Rw="
        }).Ticks.Should().Be(1609974495);
    }
}