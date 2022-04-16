﻿using Linguard.Core.Configuration;
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

    private IWireguardOptions Options => _configurationManager.Configuration.Wireguard;

    public void StartInterface(Interface iface) {
        if (_systemWrapper.IsInterfaceUp(iface)) return;
        var filepath = _configurationManager.Configuration.Wireguard.GetInterfaceConfigurationFile(iface).FullName;
        _systemWrapper.WriteAllText(filepath, WireguardUtils.GenerateWireguardConfiguration(iface));
        var result = _systemWrapper
            .RunCommand($"sudo {Options.WireguardQuickBin} up {iface.Name}");
        if (!result.Success) throw new WireguardException(result.Stderr);
    }

    public void StopInterface(Interface iface) {
        if (_systemWrapper.IsInterfaceDown(iface)) return;
        var result = _systemWrapper
            .RunCommand($"sudo {Options.WireguardQuickBin} down {iface.Name}");
        if (!result.Success) throw new WireguardException(result.Stderr);
    }

    public void AddClient(Interface iface, Client client) {
        var cmd = $"sudo {Options.WireguardQuickBin} set {iface.Name} peer {client.PublicKey} " + 
                  $"allowed-ips {string.Join(",", client.AllowedIPs)}";
        var result = _systemWrapper.RunCommand(cmd);
        if (!result.Success) throw new WireguardException(result.Stderr);
    }

    public void RemoveClient(Client client) {
        var iface = Options.GetInterface(client);
        var cmd = $"sudo {Options.WireguardQuickBin} set {iface.Name} peer {client.PublicKey} remove";
        var result = _systemWrapper.RunCommand(cmd);
        if (!result.Success) throw new WireguardException(result.Stderr);
    }
    
    public void RemoveInterface(Interface iface) {
        StopInterface(iface);
        var file = _configurationManager.Configuration.Wireguard.GetInterfaceConfigurationFile(iface);
        if (!file.Exists) return;
        file.Delete();
    }

    public string GeneratePrivateKey() {
        var result = _systemWrapper
            .RunCommand($"sudo {Options.WireguardBin} genkey");
        if (!result.Success) throw new WireguardException(result.Stderr);
        return result.Stdout;
    }
    
    public string GeneratePublicKey(string privateKey) {
        var result = _systemWrapper
            .RunCommand($"echo {privateKey} | sudo {Options.WireguardBin} pubkey");
        if (!result.Success) throw new WireguardException(result.Stderr);
        return result.Stdout;
    }

    public DateTime GetLastHandshake(Client client) {
        var rawData = _systemWrapper
            .RunCommand($"{Options.WireguardBin} show {Options.GetInterface(client).Name} dump")
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
        foreach (var iface in Options.Interfaces) {
            data.AddRange(GetTrafficData(iface));
        }
        return data;
    }
    
    public TrafficData? GetTrafficData(Client client) {
        var data = GetTrafficData(Options.GetInterface(client));
        return data.SingleOrDefault(e => e.Peer.Equals(client));
    }

    public IEnumerable<TrafficData> GetTrafficData(Interface iface) {
        var rawData = _systemWrapper
            .RunCommand($"{Options.WireguardBin} show {iface.Name} dump")
            .Stdout;
        return string.IsNullOrEmpty(rawData)
            ? Enumerable.Empty<TrafficData>()
            : WireguardDumpParser.GetTrafficData(rawData, iface);
    }
}