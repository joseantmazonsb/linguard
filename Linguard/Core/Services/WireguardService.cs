using System.Linq.Expressions;
using System.Net.NetworkInformation;
using System.Text;
using System.Text.RegularExpressions;
using Linguard.Core.Configuration;
using Linguard.Core.Managers;
using Linguard.Core.Models;
using Linguard.Core.Models.Wireguard;
using Linguard.Core.OS;
using Linguard.Core.Utils;

namespace Linguard.Core.Services; 

public class WireguardService : IWireguardService {
    private readonly IConfigurationManager _configurationManager;
    private readonly ICommandRunner _commandRunner;
    
    public WireguardService(IConfigurationManager configurationManager, ICommandRunner commandRunner) {
        _configurationManager = configurationManager;
        _commandRunner = commandRunner;
    }

    private IWireguardConfiguration Configuration => _configurationManager.Configuration.Wireguard;

    public Interface? GetInterface(Client client) => Configuration.Interfaces
        .SingleOrDefault(i => i.Clients.Contains(client));

    public void StartInterface(Interface @interface) {
        var result = _commandRunner
            .Run($"sudo {Configuration.WireguardQuickBin} up {@interface.Name}");
        if (!result.Success) throw new Exception(result.Stderr);
    }

    public void StopInterface(Interface @interface) {
        var result = _commandRunner
            .Run($"sudo {Configuration.WireguardQuickBin} down {@interface.Name}");
        if (!result.Success) throw new Exception(result.Stderr);
    }

    public string? GenerateWireguardPrivateKey() {
        return _commandRunner
            .Run($"sudo {Configuration.WireguardBin} genkey").Stdout;
    }
    
    public string? GenerateWireguardPublicKey(string privateKey) {
        return _commandRunner
            .Run($"echo {privateKey} | sudo {Configuration.WireguardBin} pubkey").Stdout;
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
        var rawData = _commandRunner
            .Run($"{Configuration.WireguardBin} show {GetInterface(client).Name} dump")
            .Stdout;
        try {
            return WireguardDumpParser.GetLastHandshake(rawData, client);
        }
        catch (Exception e) {
            // TODO: log
            return default;
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
        var rawData = _commandRunner
            .Run($"{Configuration.WireguardBin} show {iface.Name} dump")
            .Stdout;
        if (string.IsNullOrEmpty(rawData)) {
            return Enumerable.Empty<TrafficData>();
        }
        return WireguardDumpParser.GetTrafficData(rawData, iface);
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

    private string GetWireguardAddress(IWireguardPeer peer) {
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