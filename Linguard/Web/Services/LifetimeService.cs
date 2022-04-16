using System.Net.NetworkInformation;
using Linguard.Core.Configuration;
using Linguard.Core.Configuration.Exceptions;
using Linguard.Core.Models.Wireguard;
using Linguard.Core.OS;
using Linguard.Core.Services;
using Linguard.Core.Utils;
using Microsoft.AspNetCore.Identity.EntityFrameworkCore;
using IConfigurationManager = Linguard.Web.Configuration.IConfigurationManager;

namespace Linguard.Web.Services; 

public class LifetimeService : ILifetimeService {

    #region Fields and properties

    private readonly ILogger<ILifetimeService> _logger;
    private readonly ISystemWrapper _system;
    private readonly IWireguardService _wireguardService;
    private readonly IConfigurationManager _configurationManager;
    private readonly IWebService _webService;
    private readonly IServiceScope _scope;
    private IWireguardOptions? Configuration 
        => _configurationManager.Configuration.Wireguard;
    
    #endregion
    
    public LifetimeService(IConfigurationManager configurationManager, IWireguardService wireguardService, 
        ILogger<LifetimeService> logger, ISystemWrapper system, IWebService webService, IServiceScopeFactory scopeFactory) {
        _configurationManager = configurationManager;
        _wireguardService = wireguardService;
        _logger = logger;
        _system = system;
        _webService = webService;
        _scope = scopeFactory.CreateScope();
    }

    public Task OnAppStarted() {
        _logger.LogInformation($"{AssemblyInfo.Product} v{AssemblyInfo.Version.ProductVersion} is booting up...");
        //await Task.WhenAll(new Task(InitializeDatabases), new Task(LoadPlugins));
        LoadConfiguration();
        InitializeDatabases();
        InitializePlugins();
        StartInterfaces();
        _logger.LogInformation($"{AssemblyInfo.Product} is ready.");
        return Task.CompletedTask;
    }

    public Task OnAppStopping() {
        _logger.LogInformation("Shutting down...");
        StopInterfaces();
        return Task.CompletedTask;
    }
    
    public Task OnAppStopped() {
        _logger.LogInformation("Shutdown completed.");
        return Task.CompletedTask;
    }
    
    #region Auxiliary methods
    
    private void InitializeDatabases() {
        _logger.LogDebug("Initializing databases...");
        var context = _scope.ServiceProvider.GetService<IdentityDbContext>();
        context?.Database.EnsureCreated();
        _logger.LogDebug("Databases initialized.");
    }

    private void InitializePlugins() {
        _logger.LogDebug("Initializing plugins...");
        _configurationManager.PluginEngine.InitializePlugins(_configurationManager);
        _logger.LogDebug("Plugins initialized.");
    }
    
    private void LoadConfiguration() {
        try {
            _logger.LogDebug("Loading configuration...");
            var manager = _scope.ServiceProvider.GetService<ConfigurationManager>();
            var configurationSource = manager
                .GetSection(AssemblyInfo.Product)
                .GetSection(nameof(IConfigurationManager.ConfigurationSource))
                .Value;
            _configurationManager.ConfigurationSource = configurationSource;
            _configurationManager.Load();
            _webService.IsSetupNeeded = false;
            _logger.LogDebug("Configuration loaded.");
        }
        catch (ConfigurationNotLoadedError e) {
            _logger.LogWarning(e, "Unable to load configuration. Using defaults");
            _configurationManager.LoadDefaults();
        }
    }

    private void StartInterfaces() {
        var interfaces = Configuration.Interfaces
            .Where(i => i.Auto)
            .ToList();
        if (!interfaces.Any()) return;
        _logger.LogInformation("Starting all interfaces marked as auto...");
        var started = 0;
        foreach (var iface in interfaces) {
            try {
                _wireguardService.StartInterface(iface);
                started++;
            }
            catch (Exception e) {
                _logger.LogError(e, $"Unable to start '{iface.Name}'.");
            }
        }
        _logger.LogInformation($"{started} interfaces were successfully started.");
    }
    
    private void StopInterfaces() {
        var interfaces = GetStartedInterfaces().ToList();
        if (!interfaces.Any()) return;
        _logger.LogInformation("Stopping all interfaces...");
        var stopped = 0;
        foreach (var iface in interfaces) {
            try {
                _wireguardService.StopInterface(iface);
                stopped++;
            }
            catch (Exception e) {
                _logger.LogError(e, $"Unable to stop '{iface.Name}'.");
            }
        }
        _logger.LogInformation($"{stopped} interfaces were successfully stopped.");
    }

    private IEnumerable<Interface> GetStartedInterfaces() {
        var networkInterfaces = _system.NetworkInterfaces
            .Where(i => i.OperationalStatus == OperationalStatus.Up);
        return Configuration.Interfaces
            .Where(i => networkInterfaces.Any(ni => ni.Name.Equals(i.Name)));
    }

    #endregion
    
}