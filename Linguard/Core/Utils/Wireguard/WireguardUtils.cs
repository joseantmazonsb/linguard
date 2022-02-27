using System.Net.NetworkInformation;
using System.Text;
using Linguard.Core.Models.Wireguard;

namespace Linguard.Core.Utils.Wireguard; 

public static class WireguardUtils {

    public static string[] GenerateOnUpRules(string iptablesBin, string interfaceName, NetworkInterface gateway) {
        return new[] {
            $"{iptablesBin} -I FORWARD -i {interfaceName} -j ACCEPT",
            $"{iptablesBin} -I FORWARD -o {interfaceName} -j ACCEPT",
            $"{iptablesBin} -t nat -I POSTROUTING -o {gateway.Name} -j MASQUERADE",
            "sysctl net.ipv4.ip_forward=1",
            "sysctl net.ipv6.conf.all.forwarding=1"
        };
    }

    public static string[] GenerateOnDownRules(string iptablesBin, string interfaceName, NetworkInterface gateway) {
        return new[] {
            $"{iptablesBin} -D FORWARD -i {interfaceName} -j ACCEPT",
            $"{iptablesBin} -D FORWARD -o {interfaceName} -j ACCEPT",
            $"{iptablesBin} -t nat -D POSTROUTING -o {gateway.Name} -j MASQUERADE",
        };
    }

    public static string GenerateWireguardConfiguration(IWireguardPeer peer) {
        return peer switch {
            Interface @interface => GenerateWireguardConfiguration(@interface),
            Client client => GenerateWireguardConfiguration(client),
            _ => throw new ArgumentException($"Type not supported: {peer.GetType()}")
        };
    }
    
    private static string GenerateWireguardConfiguration(Interface @interface) {
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

    private static string GenerateWireguardConfiguration(Client client) {
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