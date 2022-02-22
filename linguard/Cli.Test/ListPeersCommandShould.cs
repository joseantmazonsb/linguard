
using System.Threading.Tasks;
using Castle.Core.Internal;
using FluentAssertions;
using Linguard.Cli.Commands;
using Linguard.Core.Managers;
using Linguard.Core.Models.Wireguard;
using Linguard.Core.Services;
using Moq;
using Typin.Attributes;
using Xunit;

namespace Cli.Test; 

public class ListPeersCommandShould {
    
    private static readonly Mock<IWireguardService> WireguardServiceMock = new();
    
    [Fact]
    public async Task ListOnePeer() {
        var command = typeof(ListClientsCommand);
        var commandName = command.GetAttribute<CommandAttribute>().Name!;
        var app = Utils.BuildTestApp(command);
        var iface = GenerateInterface(app.ConfigurationManager);
        app.ConfigurationManager.Configuration.Wireguard.Interfaces.Add(iface);
        var peer = GeneratePeer(iface);
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
        var peer = GeneratePeer(iface1);
        iface1.Clients.Add(peer);
        iface2.Clients.Add(GeneratePeer(iface2));
        
        var commandLine = $"{commandName} --interface {iface1.Name}";
        
        await app.App.RunAsync(commandLine);
        var errors = app.Error.GetString();
        errors.Should().BeEmpty();

        var output = app.Output.GetString().Trim();
        output.Should().Be(peer.Brief());
    }

    private Interface GenerateInterface(IConfigurationManager configuration) {
        return new DefaultInterfaceGenerator(configuration, WireguardServiceMock.Object).Generate();
    }
    
    private Client GeneratePeer(Interface iface) {
        return new DefaultClientGenerator(WireguardServiceMock.Object).Generate(iface);
    }
}