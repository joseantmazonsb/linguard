
using System.Threading.Tasks;
using Castle.Core.Internal;
using FluentAssertions;
using Linguard.Cli.Commands;
using Linguard.Core.Configuration;
using Linguard.Core.Managers;
using Linguard.Core.Models.Wireguard;
using Linguard.Core.OS;
using Linguard.Core.Services;
using Moq;
using Typin.Attributes;
using Xunit;

namespace Cli.Test; 

public class ListInterfacesCommandShould {
    
    private static readonly Mock<IWireguardService> WireguardServiceMock = new();
    
    [Fact]
    public async Task ListOneInterface() {
        var command = typeof(ListInterfacesCommand);
        var commandName = command.GetAttribute<CommandAttribute>().Name!;
        var app = Utils.BuildTestApp(command);
        var iface = GenerateInterface(app.ConfigurationManager);
        app.ConfigurationManager.Configuration.GetModule<IWireguardConfiguration>()!.Interfaces.Add(iface);

        var commandLine = $"{commandName}";
        
        await app.App.RunAsync(commandLine);
        var errors = app.Error.GetString();
        errors.Should().BeEmpty();

        var output = app.Output.GetString().Trim();
        output.Should().Be(iface.Brief());
    }

    private Interface GenerateInterface(IConfigurationManager configuration) {
        return new DefaultInterfaceGenerator(configuration, WireguardServiceMock.Object, new SystemWrapper()).Generate();
    }
}