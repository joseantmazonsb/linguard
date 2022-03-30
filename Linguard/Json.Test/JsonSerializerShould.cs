using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json;
using ByteSizeLib;
using Core.Test.Mocks;
using FluentAssertions;
using Linguard.Core.Configuration;
using Linguard.Core.Drivers.TrafficStorage;
using Linguard.Core.Managers;
using Linguard.Core.Models;
using Linguard.Core.Models.Wireguard;
using Linguard.Json;
using Xunit;

namespace Json.Test;

public class JsonSerializerShould {

    private static readonly IConfigurationManager ConfigurationManager 
        = new DefaultConfigurationManager().Object;
    private static readonly ITrafficStorageDriver TrafficStorageDriver 
        = new TrafficStorageDriver();

    private static IWireguardConfiguration WireguardConfiguration =>
        ConfigurationManager.Configuration.GetModule<IWireguardConfiguration>()!;

    private const string DateTimeFormat = "yyyy-MM-dd HH:mm:ss";
    
    private JsonSerializerOptions SerializerOptions =>
        TrafficDataSerializerOptions.Build(WireguardConfiguration, DateTimeFormat);
    
    public JsonSerializerShould() {
        ConfigurationManager.Configuration.GetModule<ITrafficConfiguration>()!.StorageDriver = TrafficStorageDriver;
        
        WireguardConfiguration.Interfaces.Add(new Interface {
            Id = Guid.NewGuid(),
            Clients = new HashSet<Client> {
                new() {
                    Id = Guid.NewGuid()
                }
            }
        });
        WireguardConfiguration.Interfaces.Add(new Interface {
            Id = Guid.NewGuid(),
            Clients = new HashSet<Client> {
                new() {
                    Id = Guid.NewGuid()
                }
            }
        });
    }

    private static string ToJson(ITrafficData data) {
        return
            "{" +
            @$"""Peer"":""{data.Peer.Id}""," +
            @$"""SentData"":{data.SentData.Bytes}," +
            @$"""ReceivedData"":{data.ReceivedData.Bytes}," + 
            @$"""TimeStamp"":""{data.TimeStamp.ToString(DateTimeFormat)}""" +
            "}";
    }
    
    [Fact]
    public void SerializeTrafficData() {
        ITrafficData data = new TrafficData {
            Peer = WireguardConfiguration.Interfaces.First(),
            ReceivedData = ByteSize.FromMegaBytes(1),
            SentData = ByteSize.FromMegaBytes(2),
            TimeStamp = DateTime.UnixEpoch
        };
        var expected = ToJson(data);
        var output = JsonSerializer.Serialize(data, SerializerOptions);
        output.Should().Be(expected);
    }

    [Fact]
    public void SerializeTrafficDataList() { 
        IEnumerable<ITrafficData> data = new List<ITrafficData> {
            new TrafficData {
                Peer = WireguardConfiguration.Interfaces.First(),
                ReceivedData = ByteSize.FromMegaBytes(1),
                SentData = ByteSize.FromMegaBytes(2),
                TimeStamp = DateTime.UnixEpoch
            },
            new TrafficData {
                Peer = WireguardConfiguration.Interfaces.Last(),
                ReceivedData = ByteSize.FromMegaBytes(2),
                SentData = ByteSize.FromMegaBytes(1),
                TimeStamp = DateTime.UnixEpoch
            }
        };
        var expected = $"[{string.Join(",", data.Select(ToJson))}]";
        var output = JsonSerializer.Serialize(data, SerializerOptions);
        output.Should().Be(expected);
    }

    [Fact]
    public void DeserializeTrafficDataAsConcreteType() {
        ITrafficData expected = new TrafficData {
            Peer = WireguardConfiguration.Interfaces.First(),
            ReceivedData = ByteSize.FromMegaBytes(1),
            SentData = ByteSize.FromMegaBytes(2),
            TimeStamp = DateTime.UnixEpoch
        };
        var data = ToJson(expected);
        var output = JsonSerializer.Deserialize<ITrafficData>(data, SerializerOptions);
        output.Should().Be(expected);
    }
    
    [Fact]
    public void DeserializeTrafficDataList() {
        IEnumerable<ITrafficData> expected = new List<ITrafficData> {
            new TrafficData {
                Peer = WireguardConfiguration.Interfaces.First(),
                ReceivedData = ByteSize.FromMegaBytes(1),
                SentData = ByteSize.FromMegaBytes(2),
                TimeStamp = DateTime.UnixEpoch
            },
            new TrafficData {
                Peer = WireguardConfiguration.Interfaces.Last(),
                ReceivedData = ByteSize.FromMegaBytes(2),
                SentData = ByteSize.FromMegaBytes(1),
                TimeStamp = DateTime.UnixEpoch
            }
        };
        var data = $"[{string.Join(",", expected.Select(ToJson))}]";
        var output = JsonSerializer.Deserialize<IEnumerable<ITrafficData>>(data, SerializerOptions);
        output.Should().BeEquivalentTo(expected);
    }
}