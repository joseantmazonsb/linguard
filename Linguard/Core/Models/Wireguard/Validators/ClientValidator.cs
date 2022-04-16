using FluentValidation;
using FluentValidation.Results;
using Linguard.Core.Configuration;
using Linguard.Core.Managers;

namespace Linguard.Core.Models.Wireguard.Validators; 

public class ClientValidator : AbstractValidator<Client> {
    private readonly IConfigurationManager _configurationManager;
    private IWireguardOptions Options => _configurationManager.Configuration.Wireguard;

    public ClientValidator(IConfigurationManager configurationManager) {
        _configurationManager = configurationManager;
    }

    public override ValidationResult Validate(ValidationContext<Client> context) {
        SetNameRules(Options);
        SetAllowedIPsRules();
        SetIPv4Rules();
        SetIpv6Rules();
        SetSecondaryDnsRules();
        SetPrimaryDnsRules();
        SetEndpointRules();
        // SetPublicKeyRules(configuration);
        // SetPrivateKeyRules(configuration);
        return base.Validate(context);
    }

    private void SetPrivateKeyRules(IWireguardOptions options) {
        const string field = nameof(Client.PublicKey);
        RuleFor(c => c.PublicKey).NotEmpty()
            .WithMessage($"{field} {Validation.CannotBeEmpty}")
            .DependentRules(() => {
                RuleFor(c => c.PublicKey)
                    .Must(key => !options.Interfaces
                        .SelectMany(i => i.Clients)
                        .Select(c => c.PublicKey).Contains(key))
                    .WithMessage($"{Validation.ClientPublicKeyAlreadyInUse}.");
            });
    }

    private void SetPublicKeyRules(IWireguardOptions options) {
        const string field = nameof(Client.PrivateKey);
        RuleFor(c => c.PrivateKey).NotEmpty()
            .WithMessage($"{field} {Validation.CannotBeEmpty}")
            .DependentRules(() => {
                RuleFor(c => c.PrivateKey)
                    .Must(key => !options.Interfaces
                        .SelectMany(i => i.Clients)
                        .Select(c => c.PrivateKey).Contains(key))
                    .WithMessage($"{Validation.ClientPrivateKeyAlreadyInUse}.");
            });
    }

    private void SetEndpointRules() {
        const string field = nameof(Client.Endpoint);
        RuleFor(c => c.Endpoint).NotEmpty()
            .WithMessage($"{field} {Validation.CannotBeEmpty}");
    }

    private void SetPrimaryDnsRules() {
        const string field = nameof(Client.PrimaryDns);
        RuleFor(c => c.Endpoint).NotEmpty()
            .WithMessage($"{field} {Validation.CannotBeEmpty}");
    }

    private void SetSecondaryDnsRules() {
        // Ignore
    }

    private void SetIpv6Rules() {
        const string field = nameof(Client.IPv6Address);
        RuleFor(c => c.IPv6Address).NotEmpty()
            .When(c => c.IPv4Address == default)
            .WithMessage($"{field} {Validation.CannotBeEmpty}");
    }

    private void SetIPv4Rules() {
        const string field = nameof(Client.IPv4Address);
        RuleFor(c => c.IPv4Address).NotEmpty()
            .When(c => c.IPv6Address == default)
            .WithMessage($"{field} {Validation.CannotBeEmpty}");
    }

    private void SetAllowedIPsRules() {
        const string field = nameof(Client.AllowedIPs);
        RuleFor(c => c.AllowedIPs).NotEmpty()
            .WithMessage($"{field} {Validation.CannotBeEmpty}");
    }
    
    private void SetNameRules(IWireguardOptions options) {
        const string field = nameof(Client.Name);
        RuleFor(c => c.Name).NotEmpty()
            .WithMessage($"{field} {Validation.CannotBeEmpty}.")
            .DependentRules(() => {
                RuleFor(c => c.Name)
                    .Must((client, name) => !options.Interfaces
                        .SelectMany(i => i.Clients)
                        .Where(c => c.PublicKey != client.PublicKey)
                        .Select(c => c.Name).Contains(name))
                    .WithMessage($"{Validation.ClientNameAlreadyInUse}.");
            });
    }
}