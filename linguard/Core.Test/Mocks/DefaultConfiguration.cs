using System.Collections.Generic;
using Linguard.Core.Configuration;
using Linguard.Core.Drivers.TrafficStorage;
using Linguard.Core.Models.Wireguard;
using Moq;

namespace Core.Test.Mocks;

public class DefaultConfiguration : Mock<IConfiguration> {

    public DefaultConfiguration() {
        SetupProperty(c => c.Wireguard, new Mock<IWireguardConfiguration>().
            SetupProperty(c => c.Interfaces, new HashSet<Interface>())
            .Object);
        SetupProperty(c => c.Logging, new Mock<ILoggingConfiguration>().Object);
        SetupProperty(c => c.Traffic, new Mock<ITrafficConfiguration>()
            .SetupProperty(c => c.StorageDriver, new Mock<ITrafficStorageDriver>().Object)
            .Object);
        SetupProperty(c => c.Web, new Mock<IWebConfiguration>().Object);
    }
}