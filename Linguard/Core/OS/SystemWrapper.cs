using System.Management.Automation;
using System.Net.NetworkInformation;
using Linguard.Core.Configuration;
using Linguard.Core.Managers;
using Linguard.Core.Models.Wireguard;
using Linguard.Core.Services.Exceptions;
using Linguard.Core.Utils.Wireguard;

namespace Linguard.Core.OS; 

public class SystemWrapper : ISystemWrapper {
    private readonly IConfigurationManager _configurationManager;

    public SystemWrapper(IConfigurationManager configurationManager) {
        _configurationManager = configurationManager;
    }

    private IWireguardConfiguration Configuration => _configurationManager.Configuration.Wireguard;
    
    public IEnumerable<NetworkInterface> NetworkInterfaces => NetworkInterface.GetAllNetworkInterfaces();
    
    public ICommandResult RunCommand(string command) {
        var ps = PowerShell.Create();
        var results = ps.AddScript(command).Invoke();
        var stdout = string.Join(Environment.NewLine, results);
        var stderr = string.Join(Environment.NewLine, ps.Streams.Error);
        return new CommandResult(stdout, stderr, !ps.HadErrors);
    }

    public void AddNetworkInterface(Interface iface) {
        var filepath = _configurationManager.WorkingDirectory.GetInterfaceConfigurationFile(iface).FullName;
        File.WriteAllText(filepath, WireguardUtils.GenerateWireguardConfiguration(iface));
        var result = RunCommand($"sudo {Configuration.WireguardQuickBin} up {filepath}");
        if (!result.Success) throw new WireguardException(result.Stderr);
    }

    public void RemoveNetworkInterface(Interface iface) {
        var result = RunCommand($"sudo {Configuration.WireguardQuickBin} down {iface.Name}");
        if (!result.Success) throw new WireguardException(result.Stderr);
        _configurationManager.WorkingDirectory.GetInterfaceConfigurationFile(iface).Delete();
    }
    
    public bool IsInterfaceUp(Interface iface) {
        return NetworkInterfaces
            .Any(i => i.Name.Equals(iface.Name) && i.OperationalStatus == OperationalStatus.Up);
    }

    public bool IsInterfaceDown(Interface iface) {
        return !IsInterfaceUp(iface);
    }
}