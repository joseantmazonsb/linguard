using System.Net.NetworkInformation;
using Linguard.Core.Models.Wireguard;

namespace Linguard.Core.OS;

/// <summary>
/// An abstraction of the system running the app.
/// </summary>
public interface ISystemWrapper {
    IEnumerable<NetworkInterface> NetworkInterfaces { get; }
    ICommandResult RunCommand(string command);
    void AddNetworkInterface(Interface iface);
    void RemoveNetworkInterface(Interface iface);
    bool IsInterfaceUp(Interface iface);
    bool IsInterfaceDown(Interface iface);
    void WriteAllText(string path, string text);
}