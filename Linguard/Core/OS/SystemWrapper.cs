using System.Management.Automation;
using System.Net.NetworkInformation;
using Linguard.Core.Models.Wireguard;

namespace Linguard.Core.OS; 

public class SystemWrapper : ISystemWrapper {

    public IEnumerable<NetworkInterface> NetworkInterfaces => NetworkInterface.GetAllNetworkInterfaces();
    
    public ICommandResult RunCommand(string command) {
        var ps = PowerShell.Create();
        var results = ps.AddScript(command).Invoke();
        var stdout = string.Join(Environment.NewLine, results);
        var stderr = string.Join(Environment.NewLine, ps.Streams.Error);
        return new CommandResult(stdout, stderr, !ps.HadErrors);
    }

    public void AddNetworkInterface(Interface iface) {
        throw new NotImplementedException();
    }

    public void RemoveNetworkInterface(Interface iface) {
        throw new NotImplementedException();
    }

    public bool IsInterfaceUp(Interface iface) {
        return NetworkInterfaces
            .Any(i => i.Name.Equals(iface.Name) && i.OperationalStatus == OperationalStatus.Up);
    }

    public bool IsInterfaceDown(Interface iface) {
        return !IsInterfaceUp(iface);
    }

    public void WriteAllText(string path, string text) {
        File.WriteAllText(path, text);
    }
}