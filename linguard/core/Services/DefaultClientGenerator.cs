﻿using System.Net;
using Bogus;
using Linguard.Core.Models.Wireguard;

namespace Linguard.Core.Services; 

public class DefaultClientGenerator : IClientGenerator {
    private readonly IWireguardService _wireguard;

    public DefaultClientGenerator(IWireguardService wireguard) {
        _wireguard = wireguard;
    }

    public Client Generate(Interface iface) {
        return new Faker<Client>()
            .RuleFor(c => c.Nat, false)
            .RuleFor(c => c.Description, f => f.Lorem.Sentence())
            .RuleFor(c => c.PrimaryDns, new Uri("8.8.8.8", UriKind.RelativeOrAbsolute))
            .RuleFor(c => c.SecondaryDns, new Uri("8.8.4.4", UriKind.RelativeOrAbsolute))
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
            .Generate();
    }
}