using Linguard.Core.Configuration;
using Linguard.Core.Managers;
using Linguard.Core.Models;
using Linguard.Core.Models.Wireguard;
using Linguard.Core.OS;
using Linguard.Core.Services.Exceptions;
using Linguard.Core.Utils.Wireguard;

namespace Linguard.Core.Services; 

public class WireguardService : IWireguardService {
    private readonly IConfigurationManager _configurationManager;
    private readonly ISystemWrapper _systemWrapper;

    public WireguardService(IConfigurationManager configurationManager, ISystemWrapper systemWrapper) {
        _configurationManager = configurationManager;
        _systemWrapper = systemWrapper;
    }

    private IWireguardConfiguration Configuration => _configurationManager.Configuration.Wireguard;

    public void StartInterface(Interface @interface) {
        var result = _systemWrapper
            .RunCommand($"sudo {Configuration.WireguardQuickBin} up {@interface.Name}");
        if (!result.Success) throw new WireguardException(result.Stderr);
    }

    public void StopInterface(Interface @interface) {
        var result = _systemWrapper
            .RunCommand($"sudo {Configuration.WireguardQuickBin} down {@interface.Name}");
        if (!result.Success) throw new WireguardException(result.Stderr);
    }

    public void AddClient(Interface iface, Client client) {
        var cmd = $"sudo {Configuration.WireguardQuickBin} set {iface.Name} peer {client.PublicKey} " + 
                  $"allowed-ips {string.Join(",", client.AllowedIPs)}";
        var result = _systemWrapper.RunCommand(cmd);
        if (!result.Success) throw new WireguardException(result.Stderr);
    }

    public void RemoveClient(Client client) {
        var iface = Configuration.GetInterface(client);
        var cmd = $"sudo {Configuration.WireguardQuickBin} set {iface.Name} peer {client.PublicKey} remove";
        var result = _systemWrapper.RunCommand(cmd);
        if (!result.Success) throw new WireguardException(result.Stderr);
    }

    public string GenerateWireguardPrivateKey() {
        var result = _systemWrapper
            .RunCommand($"sudo {Configuration.WireguardBin} genkey");
        if (!result.Success) throw new WireguardException(result.Stderr);
        return result.Stdout;
    }
    
    public string GenerateWireguardPublicKey(string privateKey) {
        var result = _systemWrapper
            .RunCommand($"echo {privateKey} | sudo {Configuration.WireguardBin} pubkey");
        if (!result.Success) throw new WireguardException(result.Stderr);
        return result.Stdout;
    }

    public DateTime GetLastHandshake(Client client) {
        var rawData = _systemWrapper
            .RunCommand($"{Configuration.WireguardBin} show {Configuration.GetInterface(client).Name} dump")
            .Stdout;
        try {
            return WireguardDumpParser.GetLastHandshake(rawData, client);
        }
        catch (Exception e) {
            throw new WireguardException($"Unable to obtain last handshake for client {client.Name}", e);
        }
    }
    
    public IEnumerable<TrafficData> GetTrafficData() {
        var data = new List<TrafficData>();
        foreach (var iface in Configuration.Interfaces) {
            data.AddRange(GetTrafficData(iface));
        }
        return data;
    }
    
    public TrafficData? GetTrafficData(Client client) {
        var data = GetTrafficData(Configuration.GetInterface(client));
        return data.SingleOrDefault(e => e.Peer.Equals(client));
    }

    public IEnumerable<TrafficData> GetTrafficData(Interface iface) {
        var rawData = _systemWrapper
            .RunCommand($"{Configuration.WireguardBin} show {iface.Name} dump")
            .Stdout;
        return string.IsNullOrEmpty(rawData) 
            ? Enumerable.Empty<TrafficData>() 
            : WireguardDumpParser.GetTrafficData(rawData, iface);
    }
}