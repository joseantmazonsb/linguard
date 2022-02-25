using System.Net.NetworkInformation;
using Moq;

namespace Core.Test.Mocks; 

public class NetworkInterfaceMock : Mock<NetworkInterface> {
    public NetworkInterfaceMock(string name) {
        SetupGet(i => i.Name).Returns(name);
    }
}