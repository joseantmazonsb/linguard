using Linguard.Core.Models;
using Linguard.Core.Models.Wireguard;

namespace Linguard.Core.Services; 

/// <summary>
/// Provides an abstraction layer to interact with Wireguard.
/// </summary>
public interface IWireguardService {
    void StartInterface(Interface iface);
    void StopInterface(Interface iface);
    void AddClient(Interface iface, Client client);
    void RemoveClient(Client client);
    string? GenerateWireguardPrivateKey();
    string? GenerateWireguardPublicKey(string privateKey);
    DateTime GetLastHandshake(Client client);
    IEnumerable<TrafficData> GetTrafficData();
    IEnumerable<TrafficData> GetTrafficData(Interface iface);
    TrafficData? GetTrafficData(Client client);
}