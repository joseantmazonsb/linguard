using System;
using System.Collections.Generic;
using System.Linq;
using Linguard.Core.Configuration;
using Linguard.Core.Drivers.TrafficStorage;
using Linguard.Core.Models.Wireguard;
using Linguard.Web.Configuration;
using Moq;

namespace Web.Test.Mocks;

public sealed class DefaultConfiguration : Mock<IConfiguration> {

    public DefaultConfiguration() {
        SetupProperty(c => c.Modules, new HashSet<IConfigurationModule> {
            GetWireguardConfigurationMock().Object,
            GetLoggingConfigurationMock().Object,
            GetTrafficConfigurationMock().Object,
            GetWebConfigurationMock().Object
        });
        Setup(o => o.Clone()).Returns(Object);
        Setup(o => o.GetModule<IConfigurationModule>())
            .Returns(new InvocationFunc(invocation => {
                var type = invocation.Method.GetGenericArguments()[0];
                return Object.Modules.SingleOrDefault(m 
                    => m.GetType() == type || m.GetType().GetInterface(type.Name) != default);
            }));
    }

    private Mock<IWireguardConfiguration> GetWireguardConfigurationMock() {
        var interfaces = new HashSet<Interface>();
        var wireguardConfiguration = new Mock<IWireguardConfiguration>()
            .SetupProperty(c => c.Interfaces, interfaces)
            .SetupProperty(c => c.Endpoint,
                new Uri("vpn.example.com", UriKind.RelativeOrAbsolute))
            .SetupProperty(c => c.IptablesBin, "iptables")
            .SetupProperty(c => c.WireguardBin, "wg")
            .SetupProperty(c => c.WireguardQuickBin, "wg-quick")
            .SetupProperty(c => c.PrimaryDns,
                new Uri("8.8.8.8", UriKind.RelativeOrAbsolute))
            .SetupProperty(c => c.SecondaryDns, default);
        wireguardConfiguration.Setup(o => o.GetInterface(It.IsAny<Client>()))
            .Returns<Client>(c => 
                interfaces.SingleOrDefault(i => i.Clients.Contains(c))
            );
        wireguardConfiguration.Setup(o => o.GetInterface(It.IsAny<Guid>()))
            .Returns<Guid>(id => 
                interfaces.SingleOrDefault(i => i.Clients.Any(c => c.Id == id))
            );
        return wireguardConfiguration;
    }

    private Mock<ILoggingConfiguration> GetLoggingConfigurationMock() {
        return new Mock<ILoggingConfiguration>();
    }
    
    private Mock<IWebConfiguration> GetWebConfigurationMock() {
        return new Mock<IWebConfiguration>();
    }
    
    private Mock<ITrafficConfiguration> GetTrafficConfigurationMock() {
        var mock = new Mock<ITrafficConfiguration>()
            .SetupProperty(c => c.StorageDriver, new Mock<ITrafficStorageDriver>().Object);
        return mock;
    }
}