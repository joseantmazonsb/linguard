using System.Net.NetworkInformation;
using Core.Test.Mocks;
using Linguard.Core.Configuration;
using Linguard.Core.Managers;
using Linguard.Core.Models.Wireguard;
using Linguard.Core.Services;
using Moq;

namespace WebMock; 

public sealed class InterfaceServiceMock : Mock<IInterfaceService> {
    private readonly List<NetworkInterface> _networkInterfaces = new();
    private readonly IConfigurationManager _configurationManager;
    private IWireguardConfiguration Configuration => _configurationManager.Configuration.Wireguard; 
    public InterfaceServiceMock(IConfigurationManager configurationManager) {
        _configurationManager = configurationManager;
        SetupGet(o => o.NetworkInterfaces).Returns(_networkInterfaces);
        Setup(o => o.StartInterface(It.IsAny<Interface>()))
            .Callback<Interface>(i => {
                if (Object.NetworkInterfaces.Any(iface => iface.Name.Equals(i.Name))) {
                    return;
                }
                var mockedInterface = new NetworkInterfaceMock(i.Name, OperationalStatus.Up).Object;
                _networkInterfaces.Add(mockedInterface);
            });
        Setup(o => o.StopInterface(It.IsAny<Interface>()))
            .Callback<Interface>(i => {
                _networkInterfaces.RemoveAll(iface => iface.Name.Equals(i.Name));
            });
        Setup(o => o.IsInterfaceDown(It.IsAny<Interface>()))
            .Returns<Interface>(i => !Object.NetworkInterfaces.Any(iface => iface.Name.Equals(i.Name)));
        Setup(o => o.IsInterfaceUp(It.IsAny<Interface>()))
            .Returns<Interface>(i => !Object.IsInterfaceDown(i));
        Setup(o => o.GetInterface(It.IsAny<Client>()))
            .Returns<Client>(c => Configuration.Interfaces.SingleOrDefault(i => i.Clients.Contains(c)));
    }
}