using Bogus;
using Linguard.Core.Configuration;
using Linguard.Core.Managers;
using Linguard.Core.Models.Wireguard;
using Linguard.Core.Services.Exceptions;

namespace Linguard.Core.Services; 

public class WireguardConfigParser : IWireguardConfigParser {
    private const StringSplitOptions SplitOptions = 
        StringSplitOptions.TrimEntries | StringSplitOptions.RemoveEmptyEntries;
    
    private readonly IConfigurationManager _configurationManager;
    private readonly IWireguardService _wireguardService;
    private readonly Faker _faker;

    public WireguardConfigParser(IConfigurationManager configurationManager, 
        IWireguardService wireguardService, Faker faker) {
        _configurationManager = configurationManager;
        _wireguardService = wireguardService;
        _faker = faker;
    }

    private IWireguardOptions Options => _configurationManager.Configuration.Wireguard;
    
    /// <summary>
    /// Valid sections in a Wireguard configuration file.
    /// </summary>
    private enum WireguardSection {
        Interface, 
        Peer
    }

    /// <summary>
    /// Valid configuration settings for an <c>[Interface]</c> section.
    /// </summary>
    private enum WireguardInterfaceConfigurationOption {
        Address, ListenPort, PrivateKey, Dns, 
        Table, Mtu, PreDown, PreUp, PostDown, PostUp,
    }
    
    /// <summary>
    /// Valid configuration settings for a <c>[Peer]</c> section.
    /// </summary>
    private enum WireguardPeerConfigurationOption {
        AllowedIPs, Endpoint, PublicKey, PersistentKeepalive
    }

    abstract class WireguardConfigurationSetting {

        protected WireguardConfigurationSetting(string name, string value) {
            Value = value;
        }
        public string Value { get; }
    }
    
    class WireguardInterfaceSetting : WireguardConfigurationSetting {
        public WireguardInterfaceSetting(string name, string value) : base(name, value) {
            if (!Enum.TryParse<WireguardInterfaceConfigurationOption>(name, true, out var option)) {
                throw new WireguardConfigurationParsingError($"Unknown option: '{name}'");
            }
            Name = option;
        }
        public WireguardInterfaceConfigurationOption Name { get; }
    }
    
    class WireguardPeerSetting : WireguardConfigurationSetting {
        public WireguardPeerSetting(string name, string value) : base(name, value) {
            if (!Enum.TryParse<WireguardPeerConfigurationOption>(name, true, out var option)) {
                throw new WireguardConfigurationParsingError($"Unknown option: '{name}'");
            }
            Name = option;
        }
        public WireguardPeerConfigurationOption Name { get; }
    }

    public T Parse<T>(string config) where T : IWireguardPeer {
        var lines = config.Split(Environment.NewLine, SplitOptions);
        WireguardSection section = default;
        var type = typeof(T);
        if (type == typeof(Interface)) {
            return (T) (IWireguardPeer) ParseInterface(lines);
        }
        if (type == typeof(Client)) {
            return (T) (IWireguardPeer) ParseClient(lines);
        }
        throw new NotSupportedException($"Wireguard peer type not supported: {type}");
    }

    public Interface Parse(string config, IEnumerable<string> clientsConfig) {
        var iface = Parse<Interface>(config);
        
        return iface;
    }

    private WireguardConfigurationSetting ParseLine(string line, WireguardSection section) {
        var split = line.Split("=", SplitOptions);
        if (split.Length != 2) {
            throw new WireguardConfigurationParsingError($"Invalid configuration line: '{line}'");
        }
        return section switch {
            WireguardSection.Interface => new WireguardInterfaceSetting(split[0], split[1]),
            WireguardSection.Peer => new WireguardPeerSetting(split[0], split[1]),
            _ => throw new ArgumentOutOfRangeException(nameof(section), section, null)
        };
    }

    private Interface ParseInterface(IEnumerable<string> lines) {
        var iface = new Interface();
        const StringComparison stringComparison = StringComparison.OrdinalIgnoreCase;
        const StringSplitOptions splitOptions = StringSplitOptions.TrimEntries | StringSplitOptions.RemoveEmptyEntries;
        WireguardSection section = default;
        foreach (var line in lines) {
            if (line.StartsWith("#")) {
                ParseComment(line[1..], iface);
                continue;
            }
            if (line.Equals("[Interface]", stringComparison)) {
                section = WireguardSection.Interface;
                continue;
            }
            if (line.Equals("[Peer]", stringComparison)) {
                section = WireguardSection.Peer;
                continue;
            }
            if (section == WireguardSection.Interface) {
                var setting = (WireguardInterfaceSetting) ParseLine(line, section);
                switch (setting.Name) {
                    case WireguardInterfaceConfigurationOption.Address:
                        GetIPAddresses(iface, setting);
                        break;
                    case WireguardInterfaceConfigurationOption.PrivateKey:
                        iface.PrivateKey = setting.Value;
                        iface.PublicKey = _wireguardService.GeneratePublicKey(iface.PrivateKey);
                        break;
                    case WireguardInterfaceConfigurationOption.ListenPort:
                        iface.Port = int.Parse(setting.Value);
                        break;
                    case WireguardInterfaceConfigurationOption.PostUp:
                        iface.OnUp = setting.Value.Split(";", splitOptions)
                            .Select(r => new Rule {Command = r})
                            .ToHashSet(); 
                        break;
                    case WireguardInterfaceConfigurationOption.PostDown:
                        iface.OnDown = setting.Value.Split(";", splitOptions)
                            .Select(r => new Rule {Command = r})
                            .ToHashSet();
                        break;
                    default:
                        throw new WireguardConfigurationParsingError(
                            $"Unexpected option found: {setting.Name}");
                }
                continue;
            }
            if (section == WireguardSection.Peer) {
                var setting = (WireguardPeerSetting) ParseLine(line, section);
                switch (setting.Name) {
                    case WireguardPeerConfigurationOption.AllowedIPs:
                        break;
                    case WireguardPeerConfigurationOption.Endpoint:
                        break;
                    case WireguardPeerConfigurationOption.PublicKey:
                        break;
                    case WireguardPeerConfigurationOption.PersistentKeepalive:
                        break;
                    default:
                        throw new ArgumentOutOfRangeException();
                }
            }
        }

        return iface;
    }
    
    private Client ParseClient(IEnumerable<string> lines) {
        var client = new Client {
            Name = _faker.Person.FullName
        };
        Interface? iface = default;
        const StringComparison stringComparison = StringComparison.OrdinalIgnoreCase;
        WireguardSection section = default;
        foreach (var line in lines) {
            if (line.StartsWith("#")) {
                ParseComment(line[1..], client);
                continue;
            }
            if (line.Equals("[Interface]", stringComparison)) {
                section = WireguardSection.Interface;
                continue;
            }
            if (line.Equals("[Peer]", stringComparison)) {
                section = WireguardSection.Peer;
                continue;
            }
            if (section == WireguardSection.Interface) {
                var setting = (WireguardInterfaceSetting) ParseLine(line, section);
                switch (setting.Name) {
                    case WireguardInterfaceConfigurationOption.Address:
                        GetIPAddresses(client, setting);
                        break;
                    case WireguardInterfaceConfigurationOption.PrivateKey:
                        client.PrivateKey = setting.Value;
                        client.PublicKey = _wireguardService.GeneratePublicKey(client.PrivateKey);
                        break;
                    case WireguardInterfaceConfigurationOption.Dns:
                        GetDns(client, setting);
                        break;
                    default:
                        throw new WireguardConfigurationParsingError(
                            $"Unexpected option found: {setting.Name}");
                }
                continue;
            }
            if (section == WireguardSection.Peer) {
                var setting = (WireguardPeerSetting) ParseLine(line, section);
                switch (setting.Name) {
                    case WireguardPeerConfigurationOption.AllowedIPs:
                        client.AllowedIPs = GetAllowedIPs(setting);
                        break;
                    case WireguardPeerConfigurationOption.Endpoint:
                        client.Endpoint = new Uri(setting.Value, UriKind.RelativeOrAbsolute);
                        break;
                    case WireguardPeerConfigurationOption.PublicKey:
                        var ifacePublicKey = setting.Value;
                        iface = Options.Interfaces
                            .SingleOrDefault(i => i.PublicKey == ifacePublicKey);
                        if (iface == default) {
                            throw new WireguardConfigurationParsingError(
                                $"There is no interface whose public key is '{ifacePublicKey}'.");
                        }
                        break;
                    case WireguardPeerConfigurationOption.PersistentKeepalive:
                        client.Nat = true;
                        break;
                    default:
                        throw new WireguardConfigurationParsingError(
                            $"Unexpected option found: {setting.Name}");
                }
            }
        }
        if (iface == default) {
            throw new WireguardConfigurationParsingError("No interface defined!");
        }
        if (client.IPv4Address == default && client.IPv6Address == default) {
            throw new WireguardConfigurationParsingError("No IP addresses were provided!");
        }
        if (client.IPv4Address != default && iface.IPv4Address != default && 
            !iface.IPv4Address.Contains(client.IPv4Address)) {
            throw new WireguardConfigurationParsingError(
                $"{nameof(client.IPv4Address)} is not in interface network ({iface.IPv4Address.IPNetwork}).");
        }
        if (client.IPv6Address != default && iface.IPv6Address != default && 
            !iface.IPv6Address.Contains(client.IPv6Address)) {
            throw new WireguardConfigurationParsingError(
                $"{nameof(client.IPv6Address)} is not in interface network ({iface.IPv6Address.IPNetwork}).");
        }
        if (client.Endpoint == default) {
            client.Endpoint = iface.Endpoint ??
                              Options.Endpoint 
                              ?? throw new WireguardConfigurationParsingError("No endpoint provided!");
        }
        if (client.AllowedIPs == default) {
            client.AllowedIPs = new HashSet<IPAddressCidr> {
                client.IPv4Address == default
                ? IPAddressCidr.Parse("0.0.0.0/0")
                : IPAddressCidr.Parse(client.IPv4Address.IPAddress, IPAddressCidr.MaxIPv4Prefix),
                client.IPv6Address == default
                    ? IPAddressCidr.Parse("::0/0")
                    : IPAddressCidr.Parse(client.IPv6Address.IPAddress, IPAddressCidr.MaxIPv6Prefix)
            };
        }
        iface.Clients.Add(client);
        return client;
    }

    private static void ParseComment(string line, IWireguardPeer peer) {
        var split = line.Split("=", SplitOptions);
        if (split.Length != 2) {
            return;
        }
        if (split[0].Equals(nameof(peer.Name), StringComparison.OrdinalIgnoreCase)) {
            peer.Name = split[1];
        }
        if (split[0].Equals(nameof(peer.Description), StringComparison.OrdinalIgnoreCase)) {
            peer.Description = split[1];
        }
    }

    private static ISet<IPAddressCidr> GetAllowedIPs(WireguardConfigurationSetting setting) {
        var split = setting.Value.Split(",", SplitOptions);
        var allowedIps = new HashSet<IPAddressCidr>();
        foreach (var ip in split) {
            allowedIps.Add(IPAddressCidr.Parse(ip));
        }
        return allowedIps;
    }

    private static void GetDns(Client client, WireguardConfigurationSetting setting) {
        var split = setting.Value.Split(",", SplitOptions);
        const int maxDnsServers = 2;
        if (split.Length > maxDnsServers) {
            throw new WireguardConfigurationParsingError(
                "Invalid DNS: expected at least 1 and at most 2 " +
                $"but {split.Length} were found.");
        }
        client.PrimaryDns = new Uri(split[0], UriKind.RelativeOrAbsolute);
        if (split.Length < maxDnsServers) return;
        client.SecondaryDns = new Uri(split[1], UriKind.RelativeOrAbsolute);
    }

    private static void GetIPAddresses(IWireguardPeer peer, WireguardConfigurationSetting setting) {
        var split = setting.Value.Split(",", SplitOptions);
        if (split.Length > 2) {
            throw new WireguardConfigurationParsingError(
                "Invalid IP addresses: expected at least 1 and at most 2 " +
                $"but {split.Length} were found.");
        }
        var lastAddressWasIPv4 = false;
        var lastAddressWasIPv6 = false;
        foreach (var str in split) {
            var ip = IPAddressCidr.Parse(str);
            if (ip.IsIPv4()) {
                if (lastAddressWasIPv4) {
                    throw new WireguardConfigurationParsingError(
                        "Invalid IP addresses: unable to use 2 addresses of the same family.");
                }
                lastAddressWasIPv4 = true;
                lastAddressWasIPv6 = false;
                peer.IPv4Address = ip;
                continue;
            }
            if (ip.IsIPv6()) {
                if (lastAddressWasIPv6) {
                    throw new WireguardConfigurationParsingError(
                        "Invalid IP addresses: unable to use 2 addresses of the same family.");
                }
                lastAddressWasIPv4 = false;
                lastAddressWasIPv6 = true;
                peer.IPv6Address = ip;
            }
        }
    }
}