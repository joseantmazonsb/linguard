using System.Net.NetworkInformation;
using Bogus;
using Moq;

namespace Core.Test.Mocks; 

public class NetworkInterfaceMock : Mock<NetworkInterface> {
    public NetworkInterfaceMock(string name, OperationalStatus status = OperationalStatus.Unknown) {
        SetupGet(i => i.Name).Returns(name);
        SetupGet(i => i.OperationalStatus).Returns(status);
        var properties = new Mock<IPInterfaceProperties>();
        properties.SetupGet(o => o.UnicastAddresses)
            .Returns(new Mock<UnicastIPAddressInformationCollection>().Object);
        Setup(o => o.GetIPProperties()).Returns(properties.Object);
        Setup(o => o.GetPhysicalAddress()).Returns(new PhysicalAddress(new Faker().Random.Bytes(6)));
    }
}