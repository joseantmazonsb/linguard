using System.Text.RegularExpressions;
using FluentValidation;
using FluentValidation.Results;
using Linguard.Core.Configuration;
using Linguard.Core.Managers;
using Linguard.Core.OS;
using Linguard.Core.Utils.Comparers;

namespace Linguard.Core.Models.Wireguard.Validators; 

public class InterfaceValidator : AbstractValidator<Interface> {

    public const int MaxNameLength = 15;
    public const int MinNameLength = 2;
    
    private readonly IConfigurationManager _configurationManager;
    private IWireguardOptions Options => _configurationManager.Configuration.Wireguard;
    private readonly ISystemWrapper _system;

    public InterfaceValidator(IConfigurationManager configurationManager, ISystemWrapper system) {
        _configurationManager = configurationManager;
        _system = system;
    }

    public override ValidationResult Validate(ValidationContext<Interface> context) {
        SetNameRules(Options);
        SetPortRules(Options);
        SetIpv4Rules(Options);
        SetIpv6Rules(Options);
        SetOnUpRules();
        SetOnDownRules();
        SetGatewayRules();
        // SetPublicKeyRules(configuration);
        // SetPrivateKeyRules(configuration);
        return base.Validate(context);
    }

    private void SetPrivateKeyRules(IWireguardOptions options) {
        const string field = nameof(Interface.PublicKey);
        RuleFor(i => i.PublicKey).NotEmpty()
            .WithMessage($"{field} {Validation.CannotBeEmpty}");
    }

    private void SetPublicKeyRules(IWireguardOptions options) {
        const string field = nameof(Interface.PrivateKey);
        RuleFor(i => i.PrivateKey).NotEmpty()
            .WithMessage($"{field} {Validation.CannotBeEmpty}");
    }

    private void SetGatewayRules() {
        const string field = nameof(Interface.Gateway);
        RuleFor(i => i.Gateway).NotEmpty()
            .WithMessage($"{field} {Validation.CannotBeEmpty}")
            .DependentRules(() => {
                RuleFor(i => i.Gateway)
                    .Must(i => _system.NetworkInterfaces
                        .Contains(i, new NetworkInterfaceNameComparer()))
                    .WithMessage(Validation.InvalidGateway);
            });
    }

    private void SetOnDownRules() {
        // Ignore
    }

    private void SetOnUpRules() {
        // Ignore
    }

    private void SetIpv6Rules(IWireguardOptions options) {
        const string field = nameof(Interface.IPv6Address);
        RuleFor(i => i.IPv6Address).NotEmpty()
            .When(i => i.IPv4Address == default)
            .WithMessage($"{field} {Validation.CannotBeEmpty}");
    }

    private void SetIpv4Rules(IWireguardOptions options) {
        const string field = nameof(Interface.IPv4Address);
        RuleFor(i => i.IPv4Address).NotEmpty()
            .When(i => i.IPv6Address == default)
            .WithMessage($"{field} {Validation.CannotBeEmpty}");
    }

    private void SetPortRules(IWireguardOptions options) {
        const string field = nameof(Interface.Port);
        RuleFor(i => i.Port).NotEmpty()
            .WithMessage($"{field} {Validation.CannotBeEmpty}")
            .DependentRules(() => {
                RuleFor(i => i.Port).InclusiveBetween(1, 65535)
                    .WithMessage(Validation.InvalidPort);
            });
    }
    
    private void SetNameRules(IWireguardOptions options) {
        const string field = nameof(Interface.Name);
        RuleFor(i => i.Name).NotEmpty()
            .WithMessage($"{field} {Validation.CannotBeEmpty}.")
            .DependentRules(() => {
                var validLengthMessage =
                    string.Format(Validation.ValidLengthForInterfaceName, MinNameLength, MaxNameLength);
                RuleFor(i => i.Name).Length(MinNameLength, MaxNameLength)
                    .WithMessage($"{field} {Validation.InvalidLength}: {validLengthMessage}.");
                RuleFor(i => i.Name).Matches(new Regex(@"^[a-z][a-z\-_0-9]+$"))
                    .WithMessage($"{field} {Validation.CharactersNotAllowed}: " +
                                 $"{Validation.CharactersAllowedForInterfaceName}.");
                RuleFor(i => i.Name)
                    .Must((iface, name) => !options.Interfaces
                        .Where(i => i.PublicKey != iface.PublicKey)
                        .Select(i => i.Name).Contains(name))
                    .WithMessage($"{Validation.InterfaceNameAlreadyInUse}.");
            });
    }
}