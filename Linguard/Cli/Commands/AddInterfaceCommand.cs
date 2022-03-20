using System.Net.NetworkInformation;
using FluentValidation;
using Linguard.Cli.TypeConverters;
using Linguard.Core;
using Linguard.Core.Configuration;
using Linguard.Core.Managers;
using Linguard.Core.Models.Wireguard;
using Linguard.Core.Services;
using Microsoft.Extensions.Logging;
using Typin;
using Typin.Attributes;
using Typin.Console;

namespace Linguard.Cli.Commands; 

[Command("add interface", Description = "Add a new interface")]
public class AddInterfaceCommand : ICommand {
    protected readonly IConfigurationManager ConfigurationManager;
    protected IConfiguration Configuration => ConfigurationManager.Configuration;
    protected readonly ILogger Logger;
    protected readonly IInterfaceGenerator Generator;
    protected readonly AbstractValidator<Interface> Validator;

    public AddInterfaceCommand(IConfigurationManager configurationManager, ILogger logger, IInterfaceGenerator interfaceGenerator, 
        AbstractValidator<Interface> validator) {
        ConfigurationManager = configurationManager;
        Logger = logger;
        Generator = interfaceGenerator;
        Validator = validator;
    }

    [CommandOption("name", Description = "Name of the interface.")]
    public string? Name { get; set; } = default;
    
    [CommandOption("description", Description = "Additional information about the interface.")]
    public string? Description { get; set; } = default;
    
    [CommandOption("ipv4", Description = "IPv4 address of the interface.", 
        Converter = typeof(IPAddressCidrTypeConverter))]
    public IPAddressCidr? IPv4Address { get; set; } = default;

    [CommandOption("ipv6", Description = "IPv6 address of the interface.",
        Converter = typeof(IPAddressCidrTypeConverter))]
    public IPAddressCidr? IPv6Address { get; set; } = default;

    [CommandOption("gateway", Description = "Gateway used by the interface.",
        Converter = typeof(NetworkInterfaceTypeConverter))]
    public NetworkInterface? Gateway { get; set; } = default;

    [CommandOption("port", Description = "Port used by the interface.")]
    public int? Port { get; set; } = default;

    [CommandOption("auto", Description = "Whether to automatically start the interface when the app starts up.")]
    public bool? Auto { get; set; } = default;
    
    [CommandOption("onUp", Description = "Commands to execute right after the interface is brought up.")]
    public ISet<Rule>? OnUp { get; set; } = default;
    
    [CommandOption("onDown", Description = "Commands to execute right after the interface is brought down.")]
    public ISet<Rule>? OnDown { get; set; } = default;
    
    [CommandOption("pubkey", Description = "The peer's public key.")]
    public string? PublicKey { get; set; } = default;
    
    [CommandOption("privkey", Description = "The peer's private key.")]
    public string? PrivateKey { get; set; } = default;
    
    public virtual ValueTask ExecuteAsync(IConsole console) {
        var iface = Generator.Generate();
        ApplyParametersSetByUser(iface);
        if (!Validate(iface, console)) {
            return ValueTask.CompletedTask;
        }
        Configuration.GetModule<IWireguardConfiguration>()!.Interfaces.Add(iface);
        ConfigurationManager.Save();
        var msg = $"Added interface '{iface.Name}'.";
        Logger.LogInformation(msg);
        console.Output.WriteLine(msg);
        return ValueTask.CompletedTask;
    }

    protected bool Validate(Interface iface, IConsole console) {
        var result = Validator.Validate(iface);
        if (result.IsValid) return true;
        foreach (var error in result.Errors) {
            console.Error.WriteLine(error);
        }
        return false;
    }
    
    protected void ApplyParametersSetByUser(Interface iface) {
        if (Name != default) iface.Name = Name;
        if (Description != default) iface.Description = Description;
        if (PrivateKey != default) iface.PrivateKey = PrivateKey;
        if (PublicKey != default) iface.PublicKey = PublicKey;
        if (IPv4Address != default) iface.IPv4Address = IPv4Address;
        if (IPv6Address != default) iface.IPv6Address = IPv6Address;
        if (Auto != default) iface.Auto = Auto.Value;
        if (Gateway != default) iface.Gateway = Gateway;
        if (Port != default) iface.Port = Port.Value;
        if (OnDown != default) iface.OnDown = OnDown;
        if (OnUp != default) iface.OnUp = OnUp;
    }
}