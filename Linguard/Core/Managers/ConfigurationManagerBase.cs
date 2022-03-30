using Linguard.Core.Configuration;
using Linguard.Core.Models.Wireguard;
using Linguard.Core.OS;
using Linguard.Core.Plugins;
using Linguard.Core.Utils;
using Linguard.Log;
using Microsoft.Extensions.Logging;

namespace Linguard.Core.Managers; 

public abstract class ConfigurationManagerBase : IConfigurationManager {
    
    private readonly ISystemWrapper _systemWrapper;
    private readonly ILinguardLogger _logger;

    protected ConfigurationManagerBase(IConfiguration configuration, IWorkingDirectory workingDirectory, 
        ISystemWrapper systemWrapper, ILinguardLogger logger, IPluginEngine pluginEngine) {
        Configuration = configuration;
        WorkingDirectory = workingDirectory;
        PluginEngine = pluginEngine;
        _systemWrapper = systemWrapper;
        _logger = logger;
    }
    
    public IConfiguration Configuration { get; set; }
    public IWorkingDirectory WorkingDirectory { get; set; }
    public IPluginEngine PluginEngine { get; set; }

    public virtual void LoadDefaults() {
        LoadLoggingDefaults();
        LoadTrafficDefaults();
        LoadWireguardDefaults();
    }
    
    protected virtual void LoadLoggingDefaults() {
        var configuration = new LoggingConfiguration {
            Level = LogLevel.Information,
            DateTimeFormat = _logger.DateTimeFormat
        };
        Configuration.Modules.Add(configuration);
    }
    protected virtual void LoadTrafficDefaults() {
        var configuration = new TrafficConfiguration {
            Enabled = false
        };
        Configuration.Modules.Add(configuration);
    }
    protected virtual void LoadWireguardDefaults() {
        var configuration = new WireguardConfiguration {
            Interfaces = new HashSet<Interface>(),
            PrimaryDns = new("8.8.8.8", UriKind.RelativeOrAbsolute),
            SecondaryDns = new("8.8.4.4", UriKind.RelativeOrAbsolute)
        };
        Configuration.Modules.Add(configuration);
        var publicIp = Network.GetPublicIPAddress();
        configuration.Endpoint = publicIp == default
            ? default
            : new(publicIp.ToString(), UriKind.RelativeOrAbsolute);
        configuration.IptablesBin = _systemWrapper
            .RunCommand("whereis iptables | tr ' ' '\n' | grep bin").Stdout;
        configuration.WireguardBin = _systemWrapper
            .RunCommand("whereis wg | tr ' ' '\n' | grep bin").Stdout;
        configuration.WireguardQuickBin = _systemWrapper
            .RunCommand("whereis wg-quick | tr ' ' '\n' | grep bin").Stdout;
    }

    public abstract void Load();

    public void Save() {
        ApplyChanges();
        DoSave();
    }

    protected virtual void ApplyChanges() {
        ApplyLogChanges();

        void ApplyLogChanges() {
            var configuration = Configuration.GetModule<ILoggingConfiguration>()!;
            _logger.LogLevel = configuration.Level;
            _logger.DateTimeFormat = configuration.DateTimeFormat;
        }
    }

    protected abstract void DoSave();
    public abstract string Export();
}