using System;
using System.Collections.Generic;
using Bogus;
using ByteSizeLib;
using Linguard.Core.Configuration;
using Linguard.Core.Drivers.TrafficStorage;
using Linguard.Core.Managers;
using Linguard.Core.Models;


namespace Core.Test.Stubs;

public class TrafficStorageDriverStub : ITrafficStorageDriver {

    public string Name => "Stub driver";
    public string Description => "This is a stub driver";
    private IConfigurationManager _configurationManager;
    private readonly Faker _faker = new();
    public void Initialize(IConfigurationManager configurationManager) {
        _configurationManager = configurationManager;
    }

    public TimeSpan CollectionInterval { get; set; } = TimeSpan.FromHours(1);

    public IDictionary<string, string> AdditionalOptions { get; set; } = new Dictionary<string, string> {
        { "Fake", "Option" }
    };
    public void Save(IEnumerable<ITrafficData> data) {
        throw new NotImplementedException();
    }

    public IEnumerable<ITrafficData> Load() {
        var interfaces = _configurationManager.Configuration.Wireguard.Interfaces;
        var data = new List<ITrafficData>();
        var entries = (int) TimeSpan.FromDays(2).TotalHours;
        var timestampBase = DateTime.Now - TimeSpan.FromHours(entries);
        foreach (var iface in interfaces) {
            for (var i = 0; i < entries; i++) {
                data.Add(new TrafficData {
                    Peer = iface,
                    ReceivedData = ByteSize.FromBytes(_faker.Random.Number((int) ByteSize.BytesInMegaByte)),
                    SentData = ByteSize.FromBytes(_faker.Random.Number((int) ByteSize.BytesInMegaByte)),
                    TimeStamp = timestampBase + TimeSpan.FromHours(i)
                });
            }
        }
        return data;
    }

    public object Clone() {
        return new TrafficStorageDriverStub {
            CollectionInterval = CollectionInterval,
            AdditionalOptions = new Dictionary<string, string>(AdditionalOptions)
        };
    }
}