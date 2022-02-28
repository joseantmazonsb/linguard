using System.Collections.Generic;
using System.Linq;
using Linguard.Core.Configuration;
using Linguard.Core.Drivers.TrafficStorage;
using Linguard.Core.Models.Wireguard;
using Moq;

namespace Core.Test.Mocks;

public sealed class DefaultConfiguration : Mock<IConfiguration> {

    public DefaultConfiguration() {
        SetupProperty(c => c.Wireguard, GetWireguardConfigurationMock().Object);
        SetupProperty(c => c.Logging, new Mock<ILoggingConfiguration>().Object);
        SetupProperty(c => c.Traffic, new Mock<ITrafficConfiguration>()
            .SetupProperty(c => c.StorageDriver, new Mock<ITrafficStorageDriver>().Object)
            .Object);
        SetupProperty(c => c.Web, new Mock<IWebConfiguration>().Object);
        Setup(o => o.Clone()).Returns(Object);
    }

    private Mock<IWireguardConfiguration> GetWireguardConfigurationMock() {
        var wireguardConfiguration = new Mock<IWireguardConfiguration>();
        var interfaces = new HashSet<Interface>();
        wireguardConfiguration.Setup(o => o.GetInterface(It.IsAny<Client>()))
            .Returns<Client>(c => 
                interfaces.SingleOrDefault(i => i.Clients.Contains(c))
            );
        wireguardConfiguration.SetupProperty(c => c.Interfaces, interfaces);
        return wireguardConfiguration;
    }
}