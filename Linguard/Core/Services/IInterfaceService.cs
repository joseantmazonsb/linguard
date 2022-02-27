using System.Net.NetworkInformation;
using Linguard.Core.Models.Wireguard;

namespace Linguard.Core.Services; 

public interface IInterfaceService {
    IEnumerable<NetworkInterface> NetworkInterfaces { get; }
    Interface? GetInterface(Client client);
    bool IsInterfaceUp(Interface iface);
    bool IsInterfaceDown(Interface iface);
    void StartInterface(Interface @interface);
    void StopInterface(Interface @interface);
}