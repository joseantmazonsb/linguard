using FluentValidation;
using Linguard.Cli.Middlewares;
using Linguard.Core.Configuration;
using Linguard.Core.Managers;
using Linguard.Core.Models.Wireguard;
using Linguard.Core.Models.Wireguard.Validators;
using Linguard.Core.OS;
using Linguard.Core.Services;
using Microsoft.Extensions.DependencyInjection;
using Typin;
using Typin.Directives;
using Typin.Modes;

namespace Linguard.Cli; 

public class CliStartup : ICliStartup {

    public void ConfigureServices(IServiceCollection services) {
        services.AddSingleton<IConfigurationManager, Yaml.YamlConfigurationManager<IConfiguration>>();
        services.AddTransient<IConfiguration, ConfigurationBase>();
        services.AddTransient<IWorkingDirectory, WorkingDirectory>();
        services.AddSingleton(DefaultYamlConfigurationSerializer.Instance);
        services.AddTransient<ISystemWrapper, SystemWrapper>();
        services.AddTransient<IWireguardService, WireguardService>();
        services.AddTransient<IInterfaceGenerator, DefaultInterfaceGenerator>();
        services.AddTransient<IClientGenerator, DefaultClientGenerator>();
        services.AddTransient<AbstractValidator<Interface>, InterfaceValidator>();
        services.AddTransient<AbstractValidator<Client>, ClientValidator>();
        // services.AddLogging(builder => {
        //     builder.UseSimpleFileLogger();
        // });
    }

    public void Configure(CliApplicationBuilder app)
    {
        app.AddCommandsFromThisAssembly()
            .AddDirective<PreviewDirective>()
            .UseMiddleware<ConfigurationSetupMiddleware>()
            .UseInteractiveMode();
    }
}