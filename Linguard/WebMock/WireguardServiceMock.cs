using Bogus;
using Linguard.Core.Models.Wireguard;
using Linguard.Core.OS;
using Linguard.Core.Services;
using Moq;

namespace WebMock; 

public class WireguardServiceMock : Mock<IWireguardService> {
    public WireguardServiceMock(ISystemWrapper systemWrapper, Faker faker) {
        Setup(o => o.StartInterface(It.IsAny<Interface>()))
            .Callback<Interface>(systemWrapper.AddNetworkInterface);
        Setup(o => o.StopInterface(It.IsAny<Interface>()))
            .Callback<Interface>(systemWrapper.RemoveNetworkInterface);
        Setup(o => o.GenerateWireguardPrivateKey())
            .Returns(faker.Lorem.Sentence());
        Setup(o => o.GenerateWireguardPublicKey(It.IsAny<string>()))
            .Returns(faker.Lorem.Sentence());
    }
}