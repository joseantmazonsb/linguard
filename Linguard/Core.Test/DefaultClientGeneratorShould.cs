using Core.Test.Mocks;
using FluentAssertions;
using FluentValidation;
using Linguard.Core.Managers;
using Linguard.Core.Models.Wireguard;
using Linguard.Core.Models.Wireguard.Validators;
using Linguard.Core.OS;
using Linguard.Core.Services;
using Moq;
using Xunit;

namespace Core.Test; 

public class DefaultClientGeneratorShould {

    private static readonly Mock<IConfigurationManager> ConfigurationManagerMock = new DefaultConfigurationManager();
    private static readonly Mock<IWireguardService> WireguardServiceMock = new();
    private static readonly ISystemWrapper SystemWrapper = new SystemWrapper(ConfigurationManagerMock.Object);

    private static IInterfaceGenerator InterfaceGenerator => 
        new DefaultInterfaceGenerator(ConfigurationManagerMock.Object, WireguardServiceMock.Object, SystemWrapper);
    private static IClientGenerator ClientGenerator => 
        new DefaultClientGenerator(WireguardServiceMock.Object, ConfigurationManagerMock.Object);
    private static AbstractValidator<Client> Validator => new ClientValidator(ConfigurationManagerMock.Object);

    [Fact]
    public void AlwaysGenerateValidClients() {
        var iface = InterfaceGenerator.Generate();
        for (var i = 0; i < 100; i++) {
            var client = ClientGenerator.Generate(iface);
            var result = Validator.Validate(client);
            result.IsValid.Should().BeTrue();
        }
    }
}