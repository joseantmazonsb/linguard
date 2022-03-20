using Linguard.Core;
using Linguard.Core.Configuration;
using Linguard.Core.Managers;
using Typin;
using Typin.Attributes;
using Typin.Console;

namespace Linguard.Cli.Commands; 

[Command("show client", Description = "Show information about an specific client.")]
public class ShowClientCommand : ICommand {
    private readonly IConfigurationManager _configurationManager;
    private IConfiguration Configuration => _configurationManager.Configuration;
    
    [CommandOption("name", Description = "Name of the client.")]
    public string Name { get; set; }
    
    [CommandOption("interface", Description = "Name of the clients's interface.")]
    public string Interface { get; set; }
    
    public ShowClientCommand(IConfigurationManager configurationManager) {
        _configurationManager = configurationManager;
    }
    
    public ValueTask ExecuteAsync(IConsole console) {
        var peer = Configuration.GetModule<IWireguardConfiguration>()!.Interfaces
            .SingleOrDefault(i => i.Name.Equals(Interface))
            ?.Clients
            .SingleOrDefault(c => c.Name.Equals(Name));
        if (peer == default) {
            console.Error.WriteLine(Validation.ClientNotFound);
            return ValueTask.CompletedTask;
        }
        console.Output.WriteLine(peer);
        return ValueTask.CompletedTask;
    }
}