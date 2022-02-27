using System.Net.NetworkInformation;
using Linguard.Core.Configuration;
using Linguard.Core.Managers;
using Linguard.Core.Models.Wireguard;
using Linguard.Core.OS;
using Linguard.Core.Services.Exceptions;

namespace Linguard.Core.Services; 

public class InterfaceService : IInterfaceService {
    
    private readonly IConfigurationManager _configurationManager;
    private readonly ICommandRunner _commandRunner;
    
    public InterfaceService(IConfigurationManager configurationManager, ICommandRunner commandRunner) {
        _configurationManager = configurationManager;
        _commandRunner = commandRunner;
    }

    private IWireguardConfiguration Configuration => _configurationManager.Configuration.Wireguard;

    public IEnumerable<NetworkInterface> NetworkInterfaces => NetworkInterface.GetAllNetworkInterfaces();

    public Interface? GetInterface(Client client) => Configuration.Interfaces
        .SingleOrDefault(i => i.Clients.Contains(client));

    public bool IsInterfaceUp(Interface iface) {
        return NetworkInterfaces
            .Any(i => i.Name.Equals(iface.Name) && i.OperationalStatus == OperationalStatus.Up);
    }

    public bool IsInterfaceDown(Interface iface) {
        return !IsInterfaceUp(iface);
    }
    
    public void StartInterface(Interface @interface) {
        var result = _commandRunner
            .Run($"sudo {Configuration.WireguardQuickBin} up {@interface.Name}");
        if (!result.Success) throw new WireguardException(result.Stderr);
    }

    public void StopInterface(Interface @interface) {
        var result = _commandRunner
            .Run($"sudo {Configuration.WireguardQuickBin} down {@interface.Name}");
        if (!result.Success) throw new WireguardException(result.Stderr);
    }
}