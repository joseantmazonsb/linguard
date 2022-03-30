using System.Collections.Generic;
using System.Linq;
using Bogus;
using ByteSizeLib;
using Linguard.Core.Configuration;
using Linguard.Core.Managers;
using Linguard.Core.Models;
using Linguard.Core.Models.Wireguard;
using Linguard.Core.OS;
using Linguard.Core.Services;
using Moq;

namespace Core.Test.Mocks; 

public class WireguardServiceMock : Mock<IWireguardService> {
    public WireguardServiceMock(IConfigurationManager manager, ISystemWrapper systemWrapper, Faker faker) {
        Setup(o => o.StartInterface(It.IsAny<Interface>()))
            .Callback<Interface>(systemWrapper.AddNetworkInterface);
        Setup(o => o.StopInterface(It.IsAny<Interface>()))
            .Callback<Interface>(systemWrapper.RemoveNetworkInterface);
        Setup(o => o.GeneratePrivateKey())
            .Returns(faker.Random.String2(20));
        Setup(o => o.GeneratePublicKey(It.IsAny<string>()))
            .Returns(faker.Random.String2(20));
        Setup(o => o.GetTrafficData(It.IsAny<Client>()))
            .Returns<Client>(client => new TrafficData {
                Peer = client,
                ReceivedData = ByteSize.FromBytes(faker.Random.Number((int) ByteSize.BytesInMegaByte)),
                SentData = ByteSize.FromBytes(faker.Random.Number((int) ByteSize.BytesInMegaByte)),
            });
        Setup(o => o.GetTrafficData(It.IsAny<Interface>()))
            .Returns<Interface>(iface => {
                if (systemWrapper.IsInterfaceDown(iface)) {
                    return Enumerable.Empty<TrafficData>();
                }
                var data = iface.Clients.Select(client => Object.GetTrafficData(client)).ToList();
                data.Add(new TrafficData {
                    Peer = iface,
                    ReceivedData = ByteSize.FromBytes(data.Sum(e => e.ReceivedData.Bytes)),
                    SentData = ByteSize.FromBytes(data.Sum(e => e.SentData.Bytes))
                });
                return data;
            });
        Setup(o => o.GetTrafficData())
            .Returns(() => {
                var data = new List<TrafficData>();
                foreach (var iface in manager.Configuration.GetModule<IWireguardConfiguration>()!.Interfaces) {
                    data.AddRange(Object.GetTrafficData(iface));
                }
                return data;
            });
    }
}