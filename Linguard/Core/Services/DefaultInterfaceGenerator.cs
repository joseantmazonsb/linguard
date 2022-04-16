using System.Net;
using System.Net.NetworkInformation;
using Bogus;
using Linguard.Core.Configuration;
using Linguard.Core.Managers;
using Linguard.Core.Models.Wireguard;
using Linguard.Core.OS;
using Linguard.Core.Utils.Wireguard;

namespace Linguard.Core.Services; 

public class DefaultInterfaceGenerator : IInterfaceGenerator {
    private readonly IWireguardService _wireguardService;
    private readonly ISystemWrapper _system;
    private readonly IConfigurationManager _configurationManager;
    private const int MaxTries = 100;
    private IWireguardOptions Options => _configurationManager.Configuration.Wireguard;

    public DefaultInterfaceGenerator(IConfigurationManager configurationManager, 
        IWireguardService wireguardService, ISystemWrapper system) {
        _configurationManager = configurationManager;
        _wireguardService = wireguardService;
        _system = system;
    }

    public Interface Generate() {
        return new Faker<Interface>()
            .RuleFor(i => i.Auto, true)
            .RuleFor(i => i.Description, f => f.Lorem.Sentence())
            .RuleFor(i => i.Gateway, f => {
                var gateways = _system.NetworkInterfaces
                    .Where(i => i.NetworkInterfaceType != NetworkInterfaceType.Loopback)
                    .ToArray();
                return f.PickRandomParam(gateways);
            })
            .RuleFor(i => i.Name, () => {
                for (var tries = 0; tries < MaxTries; tries++) {
                    var name = $"wg{tries}";
                    if (!Options.Interfaces.Select(i => i.Name).Contains(name)) {
                        return name;
                    }
                }
                return default;
            })
            .RuleFor(i => i.Port, f => {
                for (var tries = 0; tries < MaxTries; tries++) {
                    var port = f.Internet.Port();
                    if (!Options.Interfaces.Select(i => i.Port).Contains(port)) {
                        return port;
                    }
                }
                return default;
            })
            .RuleFor(i => i.OnDown, 
                (_, i) => WireguardUtils.GenerateOnDownRules(Options.IptablesBin, i.Name, i.Gateway))
            .RuleFor(i => i.OnUp, 
                (_, i) => WireguardUtils.GenerateOnUpRules(Options.IptablesBin, i.Name, i.Gateway))
            .RuleFor(i => i.PrivateKey, _wireguardService.GeneratePrivateKey())
            .RuleFor(i => i.PublicKey, 
                (_, i) => _wireguardService.GeneratePublicKey(i.PrivateKey))
            .RuleFor(i => i.IPv4Address, f => {
                for (var tries = 0; tries < MaxTries; tries++) {
                    var addr = f.Internet.IpAddress();
                    var ip = IPAddressCidr.Parse(addr, IPNetwork.Parse(addr.ToString()).Cidr);
                    var canBeUsed = true;
                    foreach (var address in Options.Interfaces.Select(i => i.IPv4Address)) {
                        if (ip.Equals(address) || address.Contains(ip.IPAddress)) {
                            canBeUsed = false;
                            break;
                        }
                    }
                    if (canBeUsed) return ip;
                }
                return default;
            })
            .RuleFor(i => i.IPv6Address, f => {
                for (var tries = 0; tries < MaxTries; tries++) {
                    var addr = f.Internet.Ipv6Address();
                    var ip = IPAddressCidr.Parse(addr, IPNetwork.Parse(addr.ToString()).Cidr);
                    var canBeUsed = true;
                    foreach (var address in Options.Interfaces.Select(i => i.IPv6Address)) {
                        if (ip.Equals(address) || address.Contains(ip.IPAddress)) {
                            canBeUsed = false;
                            break;
                        }
                    }
                    if (canBeUsed) return ip;
                }
                return default;
            })
            .RuleFor(i => i.Endpoint, Options.Endpoint)
            .RuleFor(i => i.PrimaryDns, Options.PrimaryDns)
            .RuleFor(i => i.SecondaryDns, Options.SecondaryDns)
            .RuleFor(i => i.Clients, new HashSet<Client>())
            .Generate();
    }
}