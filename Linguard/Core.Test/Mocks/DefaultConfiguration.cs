using System;
using System.Collections.Generic;
using System.Linq;
using Core.Test.Stubs;
using Linguard.Core.Configuration;
using Linguard.Core.Drivers.TrafficStorage;
using Linguard.Core.Models.Wireguard;
using Moq;

namespace Core.Test.Mocks;

public sealed class DefaultConfiguration : Mock<IConfiguration> {

    public DefaultConfiguration() {
        SetupProperty(o => o.Wireguard, GetWireguardConfigurationMock().Object);
        SetupProperty(o => o.Traffic, GetTrafficConfigurationMock().Object);
        SetupProperty(o => o.Plugins, GetPluginConfigurationMock().Object);
        Setup(o => o.Clone()).Returns(Object);
    }

    private Mock<IWireguardOptions> GetWireguardConfigurationMock() {
        var interfaces = new HashSet<Interface>();
        var mock = new Mock<IWireguardOptions>()
            .SetupProperty(c => c.Interfaces, interfaces)
            .SetupProperty(c => c.Endpoint,
                new Uri("vpn.example.com", UriKind.RelativeOrAbsolute))
            .SetupProperty(c => c.IptablesBin, "iptables")
            .SetupProperty(c => c.WireguardBin, "wg")
            .SetupProperty(c => c.WireguardQuickBin, "wg-quick")
            .SetupProperty(c => c.PrimaryDns,
                new Uri("8.8.8.8", UriKind.RelativeOrAbsolute))
            .SetupProperty(c => c.SecondaryDns, default);
        mock.Setup(o => o.GetInterface(It.IsAny<Client>()))
            .Returns<Client>(c => 
                interfaces.SingleOrDefault(i => i.Clients.Contains(c))
            );
        mock.Setup(o => o.GetInterface(It.IsAny<string>()))
            .Returns<string>(pubkey => 
                interfaces.SingleOrDefault(i => i.Clients.Any(c => c.PublicKey == pubkey))
            );
        return mock;
    }

    private Mock<IPluginOptions> GetPluginConfigurationMock() {
        var mock = new Mock<IPluginOptions>();
        return mock;
    }
    
    private Mock<ITrafficOptions> GetTrafficConfigurationMock() {
        var mock = new Mock<ITrafficOptions>()
            .SetupProperty(c => c.StorageDriver, new TrafficStorageDriverStub())
            .SetupProperty(c => c.Enabled, true);
        return mock;
    }
}