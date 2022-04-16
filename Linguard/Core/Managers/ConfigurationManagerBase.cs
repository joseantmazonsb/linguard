using Linguard.Core.Configuration;
using Linguard.Core.Models.Wireguard;
using Linguard.Core.OS;
using Linguard.Core.Plugins;
using Linguard.Core.Utils;

namespace Linguard.Core.Managers; 

public abstract class ConfigurationManagerBase : IConfigurationManager {
    
    private readonly ISystemWrapper _systemWrapper;

    protected ConfigurationManagerBase(IConfiguration configuration, ISystemWrapper systemWrapper, 
        IPluginEngine pluginEngine) {
        Configuration = configuration;
        PluginEngine = pluginEngine;
        _systemWrapper = systemWrapper;
    }
    
    public string ConfigurationSource { get; set; }
    public IConfiguration Configuration { get; set; }
    public IPluginEngine PluginEngine { get; set; }

    public virtual void LoadDefaults() {
        LoadAuthenticationDefaults();
        LoadTrafficDefaults();
        LoadWireguardDefaults();
        LoadPluginDefaults();
    }

    protected virtual void LoadAuthenticationDefaults() {
        var configuration = new AuthenticationOptions {
            DataSource = $"{AssemblyInfo.Product}.db"
        };
        Configuration.Authentication = configuration;
    }
    
    protected virtual void LoadPluginDefaults() {
        var configuration = new PluginOptions {
            PluginsDirectory = new DirectoryInfo(Path.Combine(Directory.GetCurrentDirectory(), "plugins"))
        };
        Configuration.Plugins = configuration;
    }

    protected virtual void LoadTrafficDefaults() {
        var configuration = new TrafficOptions {
            Enabled = false
        };
        Configuration.Traffic = configuration;
    }
    protected virtual void LoadWireguardDefaults() {
        var configuration = new WireguardOptions {
            Interfaces = new HashSet<Interface>(),
            PrimaryDns = new("8.8.8.8", UriKind.RelativeOrAbsolute),
            SecondaryDns = new("8.8.4.4", UriKind.RelativeOrAbsolute)
        };
        Configuration.Wireguard = configuration;
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
        DoSave();
    }

    protected abstract void DoSave();
    public abstract string Export();
}