using Linguard.Core.Configuration;
using Linguard.Core.Managers;
using Typin;
using Typin.Attributes;
using Typin.Console;

namespace Linguard.Cli.Commands; 

[Command("list interfaces", Description = "List all interfaces, showing basic information about them.")]
public class ListInterfacesCommand : ICommand {
    
    public ListInterfacesCommand(IConfigurationManager configurationManager) {
        _configurationManager = configurationManager;
    }

    private readonly IConfigurationManager _configurationManager;
    private IWireguardConfiguration Configuration => _configurationManager.Configuration.Wireguard;
    
    public ValueTask ExecuteAsync(IConsole console) {
        var interfaces = Configuration.Interfaces;
        if (!interfaces.Any()) {
            console.Output.WriteLine("There are no interfaces yet.");
            return ValueTask.CompletedTask;
        }
        var result = string.Join(Environment.NewLine, interfaces.Select(i => i.Brief()));
        console.Output.WriteLine(result);
        return ValueTask.CompletedTask;
    }
}