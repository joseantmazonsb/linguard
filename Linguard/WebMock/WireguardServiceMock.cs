using Linguard.Core.Managers;
using Linguard.Core.Models.Wireguard;
using Linguard.Core.OS;
using Linguard.Core.Services;
using Moq;

namespace WebMock; 

public class WireguardServiceMock : Mock<IWireguardService> {
    public WireguardServiceMock(IConfigurationManager configurationManager, ISystemWrapper systemWrapper) {
        Setup(o => o.StartInterface(It.IsAny<Interface>()))
            .Callback<Interface>(systemWrapper.AddNetworkInterface);
        Setup(o => o.StopInterface(It.IsAny<Interface>()))
            .Callback<Interface>(systemWrapper.RemoveNetworkInterface);
        Setup(o => o.GetInterface(It.IsAny<Client>()))
            .Returns<Client>(c => 
                configurationManager.Configuration.Wireguard.Interfaces
                    .SingleOrDefault(i => i.Clients.Contains(c))
                );
    }
}