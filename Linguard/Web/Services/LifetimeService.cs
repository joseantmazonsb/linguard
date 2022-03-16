﻿using System.Net.NetworkInformation;
using Linguard.Core.Configuration;
using Linguard.Core.Configuration.Exceptions;
using Linguard.Core.Managers;
using Linguard.Core.Models.Wireguard;
using Linguard.Core.OS;
using Linguard.Core.Services;
using Linguard.Core.Utils;
using Linguard.Log;
using Linguard.Web.Auth;
using Microsoft.EntityFrameworkCore;

namespace Linguard.Web.Services; 

public class LifetimeService : ILifetimeService {

    #region Fields and properties

    private static readonly string WorkingDirectoryEnvironmentVariable = $"{AssemblyInfo.Product}Workdir";
    
    private readonly ILinguardLogger _logger;
    private readonly ISystemWrapper _system;
    private readonly IWireguardService _wireguardService;
    private readonly IConfigurationManager _configurationManager;
    private readonly IWebService _webService;
    private readonly IServiceScope _scope;
    private IWireguardConfiguration Configuration => _configurationManager.Configuration.Wireguard;
    
    #endregion
    
    public LifetimeService(IConfigurationManager configurationManager, IWireguardService wireguardService, 
        ILinguardLogger logger, ISystemWrapper system, IWebService webService, IServiceScopeFactory scopeFactory) {
        _configurationManager = configurationManager;
        _wireguardService = wireguardService;
        _logger = logger;
        _system = system;
        _webService = webService;
        _scope = scopeFactory.CreateScope();
    }

    public void OnAppStarted() {
        _logger.LogInformation("Booting up...");
        InitializeDatabases();
        LoadConfiguration();
        StartInterfaces();
    }

    private void InitializeDatabases() {
        _logger.LogInformation("Initializing databases...");
        var context = _scope.ServiceProvider.GetService<ApplicationDbContext>();
        context?.Database.EnsureCreated();
    }

    public void OnAppStopping() {
        _logger.LogInformation("Shutting down...");
        StopInterfaces();
    }
    
    public void OnAppStopped() {
        _logger.LogInformation("Shutdown completed.");
    }
    
    #region Auxiliary methods
    
    private void LoadConfiguration() {
        _configurationManager.WorkingDirectory.BaseDirectory = GetWorkingDirectory();
        try {
            _configurationManager.Load();
            _webService.IsSetupNeeded = false;
            _logger.LogInformation("Configuration loaded.");
        }
        catch (ConfigurationNotLoadedError e) {
            _logger.LogWarning(e, "Unable to load configuration. Using defaults");
            _configurationManager.LoadDefaults();
        }
    }
    
    private DirectoryInfo GetWorkingDirectory() {
        DirectoryInfo workingDirectory;
        var useCurrentDirectory = false;
        if (Environment.GetEnvironmentVariables()[WorkingDirectoryEnvironmentVariable] is string workdir) {
            workingDirectory = new DirectoryInfo(workdir);
        }
        else {
            workingDirectory = new DirectoryInfo(Path.GetFullPath("."));
            useCurrentDirectory = true;
        }
        var logFilename = Path.ChangeExtension(AssemblyInfo.Product.ToLower(), "log");
        var logfile = new FileInfo(Path.Combine(workingDirectory.FullName, logFilename));
        _logger.Target = new FileLogTarget(logfile);
        if (useCurrentDirectory) {
            _logger.LogWarning("No working directory specified through environment variable " +
                               $"'{WorkingDirectoryEnvironmentVariable}'.");
        }
        _logger.LogInformation($"Using '{workingDirectory.FullName}' as working directory...");
        workingDirectory.Create();
        return workingDirectory;
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