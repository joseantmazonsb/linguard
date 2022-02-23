using Linguard.Core;
using Linguard.Core.Configuration;
using Linguard.Core.Managers;
using Linguard.Core.Models.Wireguard;
using Typin;
using Typin.Attributes;
using Typin.Console;

namespace Linguard.Cli.Commands; 

[Command("list clients", Description = "List all clients, showing basic information about them.")]
public class ListClientsCommand : ICommand {
    
    public ListClientsCommand(IConfigurationManager configurationManager) {
        _configurationManager = configurationManager;
    }

    private readonly IConfigurationManager _configurationManager;
    private IWireguardConfiguration Configuration => _configurationManager.Configuration.Wireguard;
    
    [CommandOption("interface", Description = "Name of the client's interface.")]
    public string? Interface { get; set; } = default;

    public ValueTask ExecuteAsync(IConsole console) {
        ICollection<Client> peers;
        if (Interface != default) {
            var iface = Configuration.Interfaces.SingleOrDefault(i => i.Name.Equals(Interface));
            if (iface == default) {
                console.Error.WriteLine(Validation.InterfaceNotFound);
                return ValueTask.CompletedTask;
            }
            peers = iface.Clients;
        }
        else {
            peers = Configuration.Interfaces.SelectMany(i => i.Clients).ToList();
        }
        if (!peers.Any()) {
            console.Output.WriteLine("There are no clients yet.");
            return ValueTask.CompletedTask;
        }
        var result = string.Join(Environment.NewLine, peers.Select(c => c.Brief()));
        console.Output.WriteLine(result);
        return ValueTask.CompletedTask;
    }
}