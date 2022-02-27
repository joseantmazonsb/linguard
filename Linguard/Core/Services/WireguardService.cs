using System.Net.NetworkInformation;
using System.Text;
using Linguard.Core.Configuration;
using Linguard.Core.Managers;
using Linguard.Core.Models;
using Linguard.Core.Models.Wireguard;
using Linguard.Core.OS;
using Linguard.Core.Services.Exceptions;
using Linguard.Core.Utils;

namespace Linguard.Core.Services; 

public class WireguardService : IWireguardService {
    private readonly IConfigurationManager _configurationManager;
    private readonly ISystemWrapper _systemWrapper;

    public WireguardService(IConfigurationManager configurationManager, ISystemWrapper systemWrapper) {
        _configurationManager = configurationManager;
        _systemWrapper = systemWrapper;
    }

    private IWireguardConfiguration Configuration => _configurationManager.Configuration.Wireguard;

    public Interface? GetInterface(Client client) => Configuration.Interfaces
        .SingleOrDefault(i => i.Clients.Contains(client));
    
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

    public void RemoveClient(Interface iface, Client client) {
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

    public string[] GenerateOnUpRules(string interfaceName, NetworkInterface gateway) {
        return new[] {
            $"{Configuration.IptablesBin} -I FORWARD -i {interfaceName} -j ACCEPT",
            $"{Configuration.IptablesBin} -I FORWARD -o {interfaceName} -j ACCEPT",
            $"{Configuration.IptablesBin} -t nat -I POSTROUTING -o {gateway.Name} -j MASQUERADE",
            "sysctl net.ipv4.ip_forward=1",
            "sysctl net.ipv6.conf.all.forwarding=1"
        };
    }

    public string[] GenerateOnDownRules(string interfaceName, NetworkInterface gateway) {
        return new[] {
            $"{Configuration.IptablesBin} -D FORWARD -i {interfaceName} -j ACCEPT",
            $"{Configuration.IptablesBin} -D FORWARD -o {interfaceName} -j ACCEPT",
            $"{Configuration.IptablesBin} -t nat -D POSTROUTING -o {gateway.Name} -j MASQUERADE",
        };
    }

    public string GenerateWireguardConfiguration(IWireguardPeer peer) {
        return peer switch {
            Interface @interface => GenerateWireguardConfiguration(@interface),
            Client client => GenerateWireguardConfiguration(client),
            _ => throw new ArgumentException($"Type not supported: {peer.GetType()}")
        };
    }

    public DateTime GetLastHandshake(Client client) {
        var rawData = _systemWrapper
            .RunCommand($"{Configuration.WireguardBin} show {GetInterface(client).Name} dump")
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
        var data = GetTrafficData(GetInterface(client));
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

    private string GenerateWireguardConfiguration(Interface @interface) {
        var interfaceSection =
            $"[Interface]{Environment.NewLine}" +
            $"PrivateKey = {@interface.PrivateKey}{Environment.NewLine}" +
            $"Address = {GetWireguardAddress(@interface)}{Environment.NewLine}" +
            $"ListenPort = {@interface.Port}{Environment.NewLine}" +
            $@"PostUp = {string.Join(Environment.NewLine+"PostUp = ", @interface.OnUp)}{Environment.NewLine}" +
            $@"PostDown = {string.Join(Environment.NewLine+"PostDown = ", @interface.OnDown)}{Environment.NewLine}" +
            $"{Environment.NewLine}";
        var peersSection = new StringBuilder();
        foreach (var peer in @interface.Clients) {
            var peerSection =
                $"[Peer]{Environment.NewLine}" +
                $"PublicKey = {peer.PublicKey}{Environment.NewLine}";
            if (peer.IPv4Address != default) {
                peerSection += $"AllowedIPs = {peer.IPv4Address.IPAddress}/32";
                if (peer.IPv6Address != default) {
                    peerSection += $", {peer.IPv6Address.IPAddress}/128{Environment.NewLine}";
                }
                else {
                    peerSection += Environment.NewLine;
                }
                peersSection.Append(peerSection);
                continue;
            }
            if (peer.IPv6Address != default) {
                peerSection += $"AllowedIPs = {peer.IPv6Address.IPAddress}/128{Environment.NewLine}";
            }
            peersSection.Append(peerSection);
        }
        return interfaceSection + peersSection;
    }

    private string GenerateWireguardConfiguration(Client client) {
        var interfaceSection =
            $"[Interface]{Environment.NewLine}" +
            $"PrivateKey = {client.PrivateKey}{Environment.NewLine}" +
            $"Address = {GetWireguardAddress(client)}{Environment.NewLine}" +
            $"DNS = {GetWireguardDns()}{Environment.NewLine}" +
            $"{Environment.NewLine}";
        var allowedIps = string.Join(", ", client.AllowedIPs.Select(ip => ip.ToString()));
        var peerSection =
            $"[Peer]{Environment.NewLine}" +
            $"PublicKey = {client.PublicKey}{Environment.NewLine}" +
            $"AllowedIPs = {allowedIps}{Environment.NewLine}" +
            $"Endpoint = {client.Endpoint}" +
            (client.Nat ? $"{Environment.NewLine}PersistentKeepalive = 25" : "");
        return interfaceSection + peerSection;
        
        string GetWireguardDns() {
            return $"{client.PrimaryDns}" + (client.SecondaryDns != default ? $", {client.SecondaryDns}" : "");
        }
    }

    private static string GetWireguardAddress(IWireguardPeer peer) {
        string address;
        if (peer.IPv4Address != default) {
            address = peer.IPv4Address.ToString();
            if (peer.IPv6Address != default) {
                address += $", {peer.IPv6Address}";
            }
        }
        else {
            address = peer.IPv6Address!.ToString();
        }
        return address;
    }
}