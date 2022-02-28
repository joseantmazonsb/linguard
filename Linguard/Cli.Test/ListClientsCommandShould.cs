
using System.Threading.Tasks;
using Castle.Core.Internal;
using FluentAssertions;
using Linguard.Cli.Commands;
using Linguard.Core.Managers;
using Linguard.Core.Models.Wireguard;
using Linguard.Core.OS;
using Linguard.Core.Services;
using Moq;
using Typin.Attributes;
using Xunit;

namespace Cli.Test; 

public class ListClientsCommandShould {
    
    private static readonly Mock<IWireguardService> WireguardServiceMock = new();
    
    [Fact]
    public async Task ListOnePeer() {
        var command = typeof(ListClientsCommand);
        var commandName = command.GetAttribute<CommandAttribute>().Name!;
        var app = Utils.BuildTestApp(command);
        var iface = GenerateInterface(app.ConfigurationManager);
        app.ConfigurationManager.Configuration.Wireguard.Interfaces.Add(iface);
        var peer = GeneratePeer(app.ConfigurationManager, iface);
        iface.Clients.Add(peer);
        
        var commandLine = $"{commandName}";
        
        await app.App.RunAsync(commandLine);
        var errors = app.Error.GetString();
        errors.Should().BeEmpty();

        var output = app.Output.GetString().Trim();
        output.Should().Be(peer.Brief());
    }
    
    [Fact]
    public async Task ListPeersForSpecificInterface() {
        var command = typeof(ListClientsCommand);
        var commandName = command.GetAttribute<CommandAttribute>().Name!;
        var app = Utils.BuildTestApp(command);

        var iface1 = GenerateInterface(app.ConfigurationManager);
        app.ConfigurationManager.Configuration.Wireguard.Interfaces.Add(iface1);
        var iface2 = GenerateInterface(app.ConfigurationManager);
        app.ConfigurationManager.Configuration.Wireguard.Interfaces.Add(iface2);
        var peer = GeneratePeer(app.ConfigurationManager, iface1);
        iface1.Clients.Add(peer);
        iface2.Clients.Add(GeneratePeer(app.ConfigurationManager, iface2));
        
        var commandLine = $"{commandName} --interface {iface1.Name}";
        
        await app.App.RunAsync(commandLine);
        var errors = app.Error.GetString();
        errors.Should().BeEmpty();

        var output = app.Output.GetString().Trim();
        output.Should().Be(peer.Brief());
    }

    private Interface GenerateInterface(IConfigurationManager configuration) {
        return new DefaultInterfaceGenerator(configuration, WireguardServiceMock.Object, new SystemWrapper(configuration))
            .Generate();
    }
    
    private Client GeneratePeer(IConfigurationManager configuration, Interface iface) {
        return new DefaultClientGenerator(WireguardServiceMock.Object, configuration).Generate(iface);
    }
}