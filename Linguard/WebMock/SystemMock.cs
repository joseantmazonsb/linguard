using System.Net.NetworkInformation;
using Core.Test.Mocks;
using Linguard.Core.Models.Wireguard;
using Linguard.Core.OS;
using Moq;

namespace WebMock; 

public class SystemMock : Mock<ISystemWrapper> {
    private readonly List<NetworkInterface> _networkInterfaces = new();
    public SystemMock() {
        SetupGet(o => o.NetworkInterfaces).Returns(_networkInterfaces);
        
        Setup(o => o.AddNetworkInterface(It.IsAny<Interface>()))
            .Callback<Interface>(i => {
                if (Object.NetworkInterfaces.Any(iface => iface.Name.Equals(i.Name))) {
                    return;
                }
                var mockedInterface = new NetworkInterfaceMock(i.Name, OperationalStatus.Up).Object;
                _networkInterfaces.Add(mockedInterface);
            });
        Setup(o => o.RemoveNetworkInterface(It.IsAny<Interface>()))
            .Callback<Interface>(i => {
                _networkInterfaces.RemoveAll(iface => iface.Name.Equals(i.Name));
            });
        Setup(o => o.RunCommand(It.IsAny<string>()))
            .Returns(new CommandResult(string.Empty, string.Empty, true));
        Setup(o => o.IsInterfaceUp(It.IsAny<Interface>()))
            .Returns<Interface>(i => 
                _networkInterfaces.Exists(iface => iface.Name.Equals(i.Name)));
        Setup(o => o.IsInterfaceDown(It.IsAny<Interface>()))
            .Returns<Interface>(i => !Object.IsInterfaceUp(i));
    }
}