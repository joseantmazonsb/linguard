using System.Net;
using System.Net.NetworkInformation;
using Bogus;
using Linguard.Core.Configuration;
using Linguard.Core.Managers;
using Linguard.Core.Models.Wireguard;

namespace Linguard.Core.Services; 

public class DefaultInterfaceGenerator : IInterfaceGenerator {
    private readonly IWireguardService _wireguard;
    private readonly IConfigurationManager _configurationManager;
    private const int MaxTries = 100;
    private IWireguardConfiguration Configuration => _configurationManager.Configuration.Wireguard;

    public DefaultInterfaceGenerator(IConfigurationManager configurationManager, IWireguardService wireguard) {
        _configurationManager = configurationManager;
        _wireguard = wireguard;
    }

    public Interface Generate() {
        return new Faker<Interface>()
            .RuleFor(i => i.Auto, true)
            .RuleFor(i => i.Description, f => f.Lorem.Sentence())
            .RuleFor(i => i.Gateway, f => {
                var gateways = NetworkInterface.GetAllNetworkInterfaces()
                    .Where(i => i.NetworkInterfaceType != NetworkInterfaceType.Loopback)
                    .ToArray();
                return f.PickRandomParam(gateways);
            })
            .RuleFor(i => i.Name, () => {
                for (var tries = 0; tries < MaxTries; tries++) {
                    var name = $"wg{tries}";
                    if (!Configuration.Interfaces.Select(i => i.Name).Contains(name)) {
                        return name;
                    }
                }
                return default;
            })
            .RuleFor(i => i.Port, f => {
                for (var tries = 0; tries < MaxTries; tries++) {
                    var port = f.Internet.Port();
                    if (!Configuration.Interfaces.Select(i => i.Port).Contains(port)) {
                        return port;
                    }
                }
                return default;
            })
            .RuleFor(i => i.OnDown, 
                (_, i) => _wireguard.GenerateOnDownRules(i.Name, i.Gateway))
            .RuleFor(i => i.OnUp, 
                (_, i) => _wireguard.GenerateOnUpRules(i.Name, i.Gateway))
            .RuleFor(i => i.PrivateKey, _wireguard.GenerateWireguardPrivateKey())
            .RuleFor(i => i.PublicKey, 
                (_, i) => _wireguard.GenerateWireguardPublicKey(i.PrivateKey))
            .RuleFor(i => i.IPv4Address, f => {
                for (var tries = 0; tries < MaxTries; tries++) {
                    var addr = f.Internet.IpAddress();
                    var ip = IPAddressCidr.Parse(addr, IPNetwork.Parse(addr.ToString()).Cidr);
                    var canBeUsed = true;
                    foreach (var address in Configuration.Interfaces.Select(i => i.IPv4Address)) {
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
                    foreach (var address in Configuration.Interfaces.Select(i => i.IPv6Address)) {
                        if (ip.Equals(address) || address.Contains(ip.IPAddress)) {
                            canBeUsed = false;
                            break;
                        }
                    }
                    if (canBeUsed) return ip;
                }
                return default;
            })
            .RuleFor(i => i.Endpoint, Configuration.Endpoint)
            .RuleFor(i => i.PrimaryDns, Configuration.PrimaryDns)
            .RuleFor(i => i.SecondaryDns, Configuration.SecondaryDns)
            .Generate();
    }
}