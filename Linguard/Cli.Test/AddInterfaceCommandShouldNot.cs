using System.Threading.Tasks;
using Bogus;
using Castle.Core.Internal;
using FluentAssertions;
using Linguard.Cli.Commands;
using Linguard.Core;
using Linguard.Core.Configuration;
using Linguard.Core.Models.Wireguard.Validators;
using Typin.Attributes;
using Xunit;

namespace Cli.Test;

public class AddInterfaceCommandShouldNot {

    [Fact]
    public async Task AddInterfaceWithEmptyName() {
        var command = typeof(AddInterfaceCommand);
        var commandName = command.GetAttribute<CommandAttribute>().Name!;
        var app = Utils.BuildTestApp(command);
        
        var commandLine = $@"{commandName} --name """;
        await app.App.RunAsync(commandLine);
        
        var error = app.Error.GetString();
        error.Should().Contain(Validation.CannotBeEmpty);
    }
    
    [Fact]
    public async Task AddTwoInterfacesWithTheSameName() {
        var command = typeof(AddInterfaceCommand);
        var commandName = command.GetAttribute<CommandAttribute>().Name!;
        var app = Utils.BuildTestApp(command);

        var commandLine = $"{commandName} --name custom_iface";
        
        await app.App.RunAsync(commandLine);
        await app.App.RunAsync(commandLine);
        var errors = app.Error.GetString();
        errors.Should().Contain(Validation.InterfaceNameAlreadyInUse);
        app.ConfigurationManager.Configuration.GetModule<IWireguardConfiguration>()!.Interfaces.Should().HaveCount(1);
    }
    
    [Fact]
    public async Task AddInterfaceWithNameTooLong() {
        var command = typeof(AddInterfaceCommand);
        var commandName = command.GetAttribute<CommandAttribute>().Name!;
        var app = Utils.BuildTestApp(command);
        var name = new Faker().Lorem.Letter(InterfaceValidator.MaxNameLength + 1);
        await app.App.RunAsync($"{commandName} --name {name}");
        var error = app.Error.GetString();
        error.Should().Contain(Validation.InvalidLength);
        error.Should().Contain(string.Format(Validation.ValidLengthForInterfaceName, 
            InterfaceValidator.MinNameLength, InterfaceValidator.MaxNameLength));
    }
    
    [Fact]
    public async Task AddInterfaceWithNameTooShort() {
        var command = typeof(AddInterfaceCommand);
        var commandName = command.GetAttribute<CommandAttribute>().Name!;
        var app = Utils.BuildTestApp(command);
        var name = new Faker().Lorem.Letter(InterfaceValidator.MinNameLength - 1);
        await app.App.RunAsync($"{commandName} --name {name}");
        var error = app.Error.GetString();
        error.Should().Contain(Validation.InvalidLength);
        error.Should().Contain(string.Format(Validation.ValidLengthForInterfaceName, 
            InterfaceValidator.MinNameLength, InterfaceValidator.MaxNameLength));
    }
}