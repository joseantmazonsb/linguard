using FluentValidation;
using Linguard.Cli.TypeConverters;
using Linguard.Core;
using Linguard.Core.Configuration;
using Linguard.Core.Managers;
using Linguard.Core.Models.Wireguard;
using Microsoft.Extensions.Logging;
using Typin;
using Typin.Attributes;
using Typin.Console;
using UriTypeConverter = Linguard.Cli.TypeConverters.UriTypeConverter;

namespace Linguard.Cli.Commands; 

[Command("edit client", Description = "Edit the configuration of an existent client.")]
public class EditClientCommand : ICommand {
    
    public EditClientCommand(IConfigurationManager configurationManager, 
        ILogger logger, AbstractValidator<Client> validator) {
        _configurationManager = configurationManager;
        _logger = logger;
        _validator = validator;
    }

    private readonly AbstractValidator<Client> _validator;
    private readonly ILogger _logger;
    private readonly IConfigurationManager _configurationManager;
    private IWireguardConfiguration Configuration 
        => _configurationManager.Configuration.GetModule<IWireguardConfiguration>()!;
    
    [CommandOption("name", Description = "Current name of the client.", IsRequired = true)]
    public string Name { get; set; }
    
    [CommandOption("newName", Description = "New name for the client.")]
    public string? NewName { get; set; }
    
    [CommandOption("description", Description = "Additional information about the client.")]
    public string? Description { get; set; }
    
    [CommandOption("ipv4", Description = "IPv4 address of the client.", 
        Converter = typeof(IPAddressCidrTypeConverter))]
    public IPAddressCidr? IPv4Address { get; set; }

    [CommandOption("ipv6", Description = "IPv6 address of the client.", 
        Converter = typeof(IPAddressCidrTypeConverter))]
    public IPAddressCidr? IPv6Address { get; set; }

    [CommandOption("allowedIps", Description = "Allowed IPs.", 
        Converter = typeof(IPAddressCidrCollectionTypeConverter))]
    public HashSet<IPAddressCidr>? AllowedIPs { get; set; }
    
    [CommandOption("nat", Description = "Whether the client is behind a NAT.")]
    public bool? Nat { get; set; }
    
    [CommandOption("dns1", Description = "Primary DNS used by the client.",
        Converter = typeof(UriTypeConverter))]
    public Uri? PrimaryDns { get; set; }
    
    [CommandOption("dns2", Description = "Secondary DNS used by the client.",
        Converter = typeof(UriTypeConverter))]
    public Uri? SecondaryDns { get; set; }
    
    [CommandOption("pubkey", Description = "The client's public key.")]
    public string? PublicKey { get; set; }
    
    [CommandOption("privkey", Description = "The client's private key.")]
    public string? PrivateKey { get; set; }
    
    [CommandOption("endpoint", Description = "Whether the client is behind a NAT.", 
        Converter = typeof(UriTypeConverter))]
    public Uri? Endpoint { get; set; }
    
    [CommandOption("interface", Description = "Name of the current interface used by the client.", IsRequired = true)]
    public string Interface { get; set; }
    
    [CommandOption("newInterface", Description = "Name of the new interface to be used by the client.")]
    public string? NewInterface { get; set; }
    
    public ValueTask ExecuteAsync(IConsole console) {
        var iface = Configuration.Interfaces.SingleOrDefault(i => i.Name.Equals(Interface));
        if (iface == default) {
            console.Error.WriteLine(Validation.InterfaceNotFound);
            return ValueTask.CompletedTask;
        }

        var peer = iface.Clients.SingleOrDefault(c => c.Name.Equals(Name));
        if (peer == default) {
            console.Error.WriteLine(Validation.ClientNotFound);
            return ValueTask.CompletedTask;
        }

        try {
            ApplyParametersSetByUser(peer);
        }
        catch (ArgumentException e) {
            console.Error.WriteLine(e.Message);
            return ValueTask.CompletedTask;
        }
        if (!Validate(peer, console)) {
            return ValueTask.CompletedTask;
        }
        
        _configurationManager.Save();
        var msg = $"Edited client '{peer.Name}' from interface '{iface.Name}'.";
        _logger.LogInformation(msg);
        console.Output.WriteLine(msg);
        return ValueTask.CompletedTask;
    }
    
    protected void ApplyParametersSetByUser(Client client) {
        if (NewName != default) client.Name = NewName;
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
        if (NewInterface == default || NewInterface.Equals(Interface)) return;
        var iface = Configuration.Interfaces
            .SingleOrDefault(i => i.Name.Equals(NewInterface));
        if (iface == default) {
            throw new ArgumentException(
                $"{Validation.InterfaceNotFound}: '{NewInterface}'"
            );
        }
        if (iface.Clients.Contains(client)) {
            throw new ArgumentException(
                $"{Validation.ClientNameAlreadyInUse} in interface '{NewInterface}'."
            );
        }
        iface.Clients.Add(client);
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