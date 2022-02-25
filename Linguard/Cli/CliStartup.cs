using FluentValidation;
using Linguard.Cli.Middlewares;
using Linguard.Core.Configuration;
using Linguard.Core.Configuration.Serialization;
using Linguard.Core.Managers;
using Linguard.Core.Models.Wireguard;
using Linguard.Core.Models.Wireguard.Validators;
using Linguard.Core.OS;
using Linguard.Core.Services;
using Linguard.Log;
using Microsoft.Extensions.DependencyInjection;
using Typin;
using Typin.Directives;
using Typin.Modes;

namespace Linguard.Cli; 

public class CliStartup : ICliStartup {

    public void ConfigureServices(IServiceCollection services) {
        services.AddSingleton<IConfigurationManager, YamlConfigurationManager>();
        services.AddTransient<IConfiguration, Configuration>();
        services.AddTransient<IWorkingDirectory, WorkingDirectory>();
        services.AddSingleton<IConfigurationSerializer>(DefaultYamlConfigurationSerializer.Instance);
        services.AddTransient<ILogger, NLogLogger>();
        services.AddTransient<ICommandRunner, CommandRunner>();
        services.AddTransient<IWireguardService, WireguardService>();
        services.AddTransient<IInterfaceGenerator, DefaultInterfaceGenerator>();
        services.AddTransient<IClientGenerator, DefaultClientGenerator>();
        services.AddTransient<AbstractValidator<Interface>, InterfaceValidator>();
        services.AddTransient<AbstractValidator<Client>, ClientValidator>();
    }

    public void Configure(CliApplicationBuilder app)
    {
        app.AddCommandsFromThisAssembly()
            .AddDirective<PreviewDirective>()
            .UseMiddleware<ConfigurationSetupMiddleware>()
            .UseInteractiveMode();
    }
}