using System.Net.NetworkInformation;
using Linguard.Core.Configuration;
using Linguard.Core.Configuration.Exceptions;
using Linguard.Core.Managers;
using Linguard.Core.Models.Wireguard;
using Linguard.Core.Services;
using Linguard.Core.Utils;

namespace Linguard.Web.Services; 

public class LifetimeService : ILifetimeService {

    #region Fields and properties

    private static readonly string WorkingDirectoryEnvironmentVariable = $"{AssemblyInfo.Product}Workdir";
    
    private readonly Log.ILogger _logger;
    private readonly IWireguardService _wireguardService;
    private readonly IConfigurationManager _configurationManager;
    private IWireguardConfiguration Configuration => _configurationManager.Configuration.Wireguard;
    
    #endregion
    
    public LifetimeService(IConfigurationManager configurationManager, IWireguardService wireguardService, Log.ILogger logger) {
        _configurationManager = configurationManager;
        _wireguardService = wireguardService;
        _logger = logger;
    }

    public void OnAppStarted() {
        _logger.Info($"Booting up {AssemblyInfo.Product}...");
        LoadConfiguration();
        StartInterfaces();
    }

    public void OnAppStopping() {
        _logger.Info($"Shutting down {AssemblyInfo.Product}...");
        StopInterfaces();
    }
    
    public void OnAppStopped() {
        _logger.Info($"{AssemblyInfo.Product}'s shutdown completed.");
    }
    
    #region Auxiliary methods
    
    private void LoadConfiguration() {
        _logger.Info("Loading configuration...");
        _configurationManager.WorkingDirectory.BaseDirectory = GetWorkingDirectory();
        try {
            _configurationManager.Load();
            _logger.Info("Configuration loaded.");
            
        }
        catch (ConfigurationNotLoadedError e) {
            _logger.Warn(e, "Unable to load configuration. Using defaults.");
            _configurationManager.LoadDefaults();
        }
    }
    
    private DirectoryInfo GetWorkingDirectory() {
        DirectoryInfo workingDirectory;
        if (Environment.GetEnvironmentVariables()[WorkingDirectoryEnvironmentVariable] is string workdir) {
            workingDirectory = new DirectoryInfo(workdir);
            _logger.Info($"Using '{workingDirectory.FullName}' as working directory...");
        }
        else {
            workingDirectory = new DirectoryInfo(Path.GetFullPath("."));
            var warn = "WARNING: No working directory specified through environment variable " +
                       $"'{WorkingDirectoryEnvironmentVariable}'. " +
                       $"The current directory, '{workingDirectory}', will be used instead.";
            _logger.Warn(warn);
        }
        workingDirectory.Create();
        return workingDirectory;
    }

    private void StartInterfaces() {
        var interfaces = Configuration.Interfaces
            .Where(i => i.Auto)
            .ToList();
        if (!interfaces.Any()) return;
        _logger.Info("Starting all interfaces marked as auto...");
        var started = 0;
        foreach (var iface in interfaces) {
            try {
                _wireguardService.StartInterface(iface);
                started++;
            }
            catch (Exception e) {
                _logger.Error(e, $"Unable to start '{iface.Name}'.");
            }
        }
        _logger.Info($"{started} interfaces were successfully started.");
    }
    
    private void StopInterfaces() {
        var interfaces = GetStartedInterfaces().ToList();
        if (!interfaces.Any()) return;
        _logger.Info("Stopping all interfaces...");
        var stopped = 0;
        foreach (var iface in interfaces) {
            try {
                _wireguardService.StopInterface(iface);
                stopped++;
            }
            catch (Exception e) {
                _logger.Error(e, $"Unable to stop '{iface.Name}'.");
            }
        }
        _logger.Info($"{stopped} interfaces were successfully stopped.");
    }

    private IEnumerable<Interface> GetStartedInterfaces() {
        var networkInterfaces = NetworkInterface.GetAllNetworkInterfaces()
            .Where(i => i.OperationalStatus == OperationalStatus.Up);
        return Configuration.Interfaces
            .Where(i => networkInterfaces.Any(ni => ni.Name.Equals(i.Name)));
    }

    #endregion
    
}