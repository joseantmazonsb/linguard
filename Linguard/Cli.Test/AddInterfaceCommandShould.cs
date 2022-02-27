using System.Threading.Tasks;
using Castle.Core.Internal;
using Core.Test.Mocks;
using FluentAssertions;
using Linguard.Cli.Commands;
using Typin.Attributes;
using Xunit;

namespace Cli.Test; 

public class AddInterfaceCommandShould {
    
    [Fact]
    public async Task CreateInterfaceWithNoArguments() {
        var command = typeof(AddInterfaceCommand);
        var commandName = command.GetAttribute<CommandAttribute>().Name!;
        var app = Utils.BuildTestApp(command);

        var commandLine = $"{commandName}";
        
        await app.App.RunAsync(commandLine);
        var errors = app.Error.GetString();
        errors.Should().BeEmpty();
        app.ConfigurationManager.Configuration.Wireguard.Interfaces.Should().NotBeEmpty();
    }
    
    [Fact]
    public async Task CreateTwoInterfacesWithNoArguments() {
        var command = typeof(AddInterfaceCommand);
        var commandName = command.GetAttribute<CommandAttribute>().Name!;
        var app = Utils.BuildTestApp(command);

        var commandLine = $"{commandName}";
        
        await app.App.RunAsync(commandLine);
        await app.App.RunAsync(commandLine);
        var errors = app.Error.GetString();
        errors.Should().BeEmpty();
        app.ConfigurationManager.Configuration.Wireguard.Interfaces.Should().HaveCount(2);
    }
    
    [Fact]
    public async Task CreateInterfaceWithDefinedName() {
        var command = typeof(AddInterfaceCommand);
        var commandName = command.GetAttribute<CommandAttribute>().Name!;
        var app = Utils.BuildTestApp(command);

        var commandLine = $"{commandName} --name custom_iface";
        
        await app.App.RunAsync(commandLine);
        var errors = app.Error.GetString();
        errors.Should().BeEmpty();
        app.ConfigurationManager.Configuration.Wireguard.Interfaces.Should().NotBeEmpty();
    }
    
    [Fact]
    public async Task CreateInterfaceWithDefinedGateway() {             
        var command = typeof(AddInterfaceCommand);
        var commandName = command.GetAttribute<CommandAttribute>().Name!;
        var app = Utils.BuildTestApp(command);

        var gateway = new NetworkInterfaceMock("eth0").Object;
        var commandLine = $"{commandName} --gateway {gateway.Name}";
        
        await app.App.RunAsync(commandLine);
        var errors = app.Error.GetString();
        errors.Should().BeEmpty();
        app.ConfigurationManager.Configuration.Wireguard.Interfaces.Should().NotBeEmpty();
    }
}