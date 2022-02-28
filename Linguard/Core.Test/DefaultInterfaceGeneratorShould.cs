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

public class DefaultInterfaceGeneratorShould {

    private static readonly Mock<IConfigurationManager> ConfigurationManagerMock = new DefaultConfigurationManager();
    private static readonly Mock<IWireguardService> WireguardServiceMock = new();
    private static readonly ISystemWrapper SystemWrapper = new SystemWrapper(ConfigurationManagerMock.Object);

    private static IInterfaceGenerator Generator =>
        new DefaultInterfaceGenerator(ConfigurationManagerMock.Object, WireguardServiceMock.Object, SystemWrapper);
    private static AbstractValidator<Interface> Validator => 
        new InterfaceValidator(ConfigurationManagerMock.Object, SystemWrapper);

    [Fact]
    public void AlwaysGenerateValidInterfaces() {
        for (var i = 0; i < 100; i++) {
            var iface = Generator.Generate();
            var result = Validator.Validate(iface);
            result.IsValid.Should().BeTrue();
        }
    }
}