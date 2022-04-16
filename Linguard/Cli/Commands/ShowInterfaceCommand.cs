using Linguard.Core;
using Linguard.Core.Configuration;
using Linguard.Core.Managers;
using Typin;
using Typin.Attributes;
using Typin.Console;

namespace Linguard.Cli.Commands; 

[Command("show interface", Description = "Show information about an specific interface.")]
public class ShowInterfacesCommand : ICommand {
    private readonly IConfigurationManager _configurationManager;
    private IConfiguration Configuration => _configurationManager.Configuration;
    
    [CommandOption("name", Description = "Name of the interface.")]
    public string? Name { get; set; } = default;
    
    public ShowInterfacesCommand(IConfigurationManager configurationManager) {
        _configurationManager = configurationManager;
    }
    
    public ValueTask ExecuteAsync(IConsole console) {
        var iface = Configuration.Wireguard
            .Interfaces.SingleOrDefault(i => i.Name.Equals(Name));
        if (iface == default) {
            console.Error.WriteLine(Validation.InterfaceNotFound);
            return ValueTask.CompletedTask;
        }
        console.Output.WriteLine(iface);
        return ValueTask.CompletedTask;
    }
}