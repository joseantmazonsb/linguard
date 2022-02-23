using FluentValidation;
using Linguard.Cli.TypeConverters;
using Linguard.Core;
using Linguard.Core.Configuration;
using Linguard.Core.Managers;
using Linguard.Core.Models.Wireguard;
using Linguard.Core.Services;
using Linguard.Log;
using Typin;
using Typin.Attributes;
using Typin.Console;
using UriTypeConverter = Linguard.Cli.TypeConverters.UriTypeConverter;

namespace Linguard.Cli.Commands; 

[Command("add client", Description = "Add a new client to an existent interface")]
public class AddClientCommand : ICommand {
    
    public AddClientCommand(IConfigurationManager configurationManager, IClientGenerator generator, 
        ILogger logger, AbstractValidator<Client> validator) {
        _configurationManager = configurationManager;
        _generator = generator;
        _logger = logger;
        _validator = validator;
    }

    private readonly AbstractValidator<Client> _validator;
    private readonly ILogger _logger;
    private readonly IClientGenerator _generator;
    private readonly IConfigurationManager _configurationManager;
    private IWireguardConfiguration Configuration => _configurationManager.Configuration.Wireguard;
    
    [CommandOption("name", Description = "Name of the peer.")]
    public string? Name { get; set; }
    
    [CommandOption("description", Description = "Additional information about the peer.")]
    public string? Description { get; set; }
    
    [CommandOption("ipv4", Description = "IPv4 address of the peer.", 
        Converter = typeof(IPAddressCidrTypeConverter))]
    public IPAddressCidr? IPv4Address { get; set; }

    [CommandOption("ipv6", Description = "IPv6 address of the peer.", 
        Converter = typeof(IPAddressCidrTypeConverter))]
    public IPAddressCidr? IPv6Address { get; set; }

    [CommandOption("allowedIps", Description = "Allowed IPs.", 
        Converter = typeof(IPAddressCidrCollectionTypeConverter))]
    public ICollection<IPAddressCidr>? AllowedIPs { get; set; }
    
    [CommandOption("nat", Description = "Whether the peer is behind a NAT.")]
    public bool? Nat { get; set; }
    
    [CommandOption("dns1", Description = "Primary DNS used by the peer.",
        Converter = typeof(UriTypeConverter))]
    public Uri? PrimaryDns { get; set; }
    
    [CommandOption("dns2", Description = "Secondary DNS used by the peer.",
        Converter = typeof(UriTypeConverter))]
    public Uri? SecondaryDns { get; set; }
    
    [CommandOption("pubkey", Description = "The peer's public key.")]
    public string? PublicKey { get; set; }
    
    [CommandOption("privkey", Description = "The peer's private key.")]
    public string? PrivateKey { get; set; }
    
    [CommandOption("endpoint", Description = "Whether the peer is behind a NAT.", 
        Converter = typeof(UriTypeConverter))]
    public Uri? Endpoint { get; set; }
    
    [CommandOption("interface", Description = "Name of the interface used by the peer.", IsRequired = true)]
    public string? Interface { get; set; }
    
    public ValueTask ExecuteAsync(IConsole console) {
        if (Interface == default) {
            console.Error.WriteLine(Validation.InterfaceNotFound);
            return ValueTask.CompletedTask;
        }
        var iface = Configuration.Interfaces.SingleOrDefault(i => i.Name.Equals(Interface));
        if (iface == default) {
            console.Error.WriteLine(Validation.InterfaceNotFound);
            return ValueTask.CompletedTask;
        }
        var client = _generator.Generate(iface);
        ApplyParametersSetByUser(client);
        if (!Validate(client, console)) {
            return ValueTask.CompletedTask;
        }
        
        iface.Clients.Add(client);
        _configurationManager.Save();
        var msg = $"Added peer '{client.Name}' to interface '{iface.Name}'.";
        _logger.Info(msg);
        console.Output.WriteLine(msg);
        return ValueTask.CompletedTask;
    }
    
    protected void ApplyParametersSetByUser(Client client) {
        if (Name != default) client.Name = Name;
        if (Description != default) client.Description = Description;
        if (PrivateKey != default) client.PrivateKey = PrivateKey;
        if (PublicKey != default) client.PublicKey = PublicKey;
        if (IPv4Address != default) client.IPv4Address = IPv4Address;
        if (IPv6Address != default) client.IPv6Address = IPv6Address;
        if (Nat != default) client.Nat = Nat.Value;
        if (PrimaryDns != default) client.PrimaryDns = PrimaryDns;
        if (SecondaryDns != default) client.SecondaryDns = SecondaryDns;
        if (AllowedIPs != default) client.AllowedIPs = AllowedIPs;
        if (Endpoint != default) client.Endpoint = Endpoint;
    }
    
    protected bool Validate(Client client, IConsole console) {
        var result = _validator.Validate(client);
        if (result.IsValid) return true;
        foreach (var error in result.Errors) {
            console.Error.WriteLine(error);
        }
        return false;
    }
}