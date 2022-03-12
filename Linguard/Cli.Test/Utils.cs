using System;
using System.Collections.Generic;
using Core.Test.Mocks;
using FluentValidation;
using Linguard.Core.Configuration;
using Linguard.Core.Managers;
using Linguard.Core.Models.Wireguard;
using Linguard.Core.Models.Wireguard.Validators;
using Linguard.Core.Services;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.DependencyInjection.Extensions;
using Microsoft.Extensions.Logging;
using Moq;
using Typin;
using Typin.Console;
using Typin.Utilities;

namespace Cli.Test;

public struct TestApp {
    public CliApplication App;
    public VirtualConsole Console;
    public MemoryStreamWriter Output;
    public MemoryStreamWriter Error;
    public IConfigurationManager ConfigurationManager;
}

public static class Utils {
    public static TestApp BuildTestApp(params Type[] commands) {
        var (console, stdout, stderr) = VirtualConsole.CreateBuffered();
        var config = new DefaultConfiguration().Object;
        var configurationManager = new DefaultConfigurationManager().Object;
        configurationManager.Configuration = config;
        var app = new CliApplicationBuilder()
            .AddCommands(commands)
            .UseConsole(console)
            .ConfigureServices(services => {
                services.AddSingleton(config);
                services.AddSingleton(configurationManager);
                services.AddSingleton(new Mock<IWorkingDirectory>().Object);
                services.AddSingleton(new Mock<IWireguardService>().Object);
                services.AddTransient<AbstractValidator<Interface>, InterfaceValidator>();
                services.AddTransient<IInterfaceGenerator, DefaultInterfaceGenerator>();
                services.AddTransient<IClientGenerator, DefaultClientGenerator>();
                services.AddTransient<AbstractValidator<Client>, ClientValidator>();
                services.AddLogging(builder => {
                    builder.Services.TryAddSingleton(new Mock<ILogger>().Object);
                });
            })
            .Build();
        return new TestApp() {
            App = app,
            Console = console,
            Error = stderr,
            Output = stdout,
            ConfigurationManager = configurationManager
        };
    }
    
    public static TestApp BuildTestApp(IEnumerable<Type> commands, Action<IServiceCollection> servicesConfiguration) {
        var (console, stdout, stderr) = VirtualConsole.CreateBuffered();
        var app = new CliApplicationBuilder()
            .AddCommands(commands)
            .UseConsole(console)
            .ConfigureServices(servicesConfiguration)
            .Build();
        return new TestApp() {
            App = app,
            Console = console,
            Error = stderr,
            Output = stdout
        };
    }
}