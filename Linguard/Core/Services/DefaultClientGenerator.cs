using System.Net;
using Bogus;
using Linguard.Core.Configuration;
using Linguard.Core.Managers;
using Linguard.Core.Models.Wireguard;
using Linguard.Core.Utils;

namespace Linguard.Core.Services; 

public class DefaultClientGenerator : IClientGenerator {
    private IWireguardConfiguration Configuration => _configurationManager.Configuration.Wireguard;
    private readonly IConfigurationManager _configurationManager;
    private readonly IWireguardService _wireguard;

    public DefaultClientGenerator(IWireguardService wireguard, IConfigurationManager configurationManager) {
        _wireguard = wireguard;
        _configurationManager = configurationManager;
    }

    public Client Generate(Interface iface) {
        return new Faker<Client>()
            .RuleFor(c => c.Id, () => {
                var clients = Configuration.Interfaces.SelectMany(i => i.Clients).ToList();
                Guid id = default;
                while (id == default || clients.Any(c => c.Id == id)) {
                    id = Guid.NewGuid();
                }
                return id;
            })
            .RuleFor(c => c.Nat, false)
            .RuleFor(c => c.Description, f => f.Lorem.Sentence())
            .RuleFor(c => c.Name, f => f.Person.FullName)
            .RuleFor(c => c.Endpoint, new Uri("vpn.example.com", UriKind.RelativeOrAbsolute))
            .RuleFor(c => c.PrivateKey, _wireguard.GenerateWireguardPrivateKey())
            .RuleFor(c => c.PublicKey, 
                (_, i) => _wireguard.GenerateWireguardPublicKey(i.PrivateKey))
            .RuleFor(c => c.IPv4Address, f => {
                var ips = iface.IPv4Address?.IPNetwork.ListIPAddress(FilterEnum.Usable);
                return ips?.Select(ip => IPAddressCidr.Parse(ip, iface.IPv4Address.Cidr))
                    .FirstOrDefault(address => !iface.Clients.Select(c => c.IPv4Address)
                        .Contains(address));
            })
            .RuleFor(c => c.IPv6Address, f => {
                var ips = iface.IPv6Address?.IPNetwork.ListIPAddress(FilterEnum.Usable);
                return ips?.Select(ip => IPAddressCidr.Parse(ip, iface.IPv6Address.Cidr))
                    .FirstOrDefault(address => !iface.Clients.Select(c => c.IPv6Address)
                        .Contains(address));
            })
            .RuleFor(c => c.AllowedIPs, (_, p) => {
                var ips = new List<IPAddressCidr>();
                if (p.IPv4Address != default) ips.Add(IPAddressCidr.Parse("0.0.0.0/0"));
                if (p.IPv6Address != default) ips.Add(IPAddressCidr.Parse("::0/0"));
                return ips;
            })
            .RuleFor(c => c.Endpoint, iface.Endpoint 
                                      ?? Configuration.Endpoint
                                      ?? new(Network.GetPublicIPAddress()?.ToString() ?? string.Empty, 
                                          UriKind.RelativeOrAbsolute))
            .RuleFor(c => c.PrimaryDns, iface.PrimaryDns 
                                        ?? Configuration.PrimaryDns 
                                        ?? new Uri("8.8.8.8", UriKind.RelativeOrAbsolute))
            .RuleFor(c => c.SecondaryDns, iface.SecondaryDns 
                                          ?? Configuration.SecondaryDns 
                                          ?? new Uri("8.8.4.4", UriKind.RelativeOrAbsolute))
            .Generate();
    }
}