﻿using Linguard.Core.Configuration;
using Linguard.Core.Drivers.TrafficStorage;
using Linguard.Core.Models;
using Linguard.Core.Models.Wireguard;
using Linguard.Core.OS;
using Linguard.Core.Utils;
using Linguard.Log;

namespace Linguard.Core.Managers; 

public abstract class ConfigurationManagerBase : IConfigurationManager {
    
    private readonly ISystemWrapper _systemWrapper;

    protected ConfigurationManagerBase(IConfiguration configuration, IWorkingDirectory workingDirectory, 
        ISystemWrapper systemWrapper) {
        Configuration = configuration;
        WorkingDirectory = workingDirectory;
        _systemWrapper = systemWrapper;
    }
    
    public IConfiguration Configuration { get; set; }
    public IWorkingDirectory WorkingDirectory { get; set; }

    public void LoadDefaults() {
        LoadWebDefaults();
        LoadLoggingDefaults();
        LoadTrafficDefaults();
        LoadWireguardDefaults();
    }

    private void LoadWebDefaults() {
        Configuration.Web.Style = Style.Default;
        Configuration.Web.LoginAttempts = 10;
        Configuration.Web.SecretKey = "";
    }
    private void LoadLoggingDefaults() {
        Configuration.Logging.Level = LogLevel.Info;
        Configuration.Logging.Overwrite = false;
    }
    private void LoadTrafficDefaults() {
        Configuration.Traffic.Enabled = true;
        Configuration.Traffic.StorageDriver = new JsonTrafficStorageDriver();
    }
    private void LoadWireguardDefaults() {
        Configuration.Wireguard.Interfaces = new HashSet<Interface>();
        Configuration.Wireguard.IptablesBin = _systemWrapper
            .RunCommand("whereis iptables | tr ' ' '\n' | grep bin").Stdout;
        Configuration.Wireguard.WireguardBin = _systemWrapper
            .RunCommand("whereis wg | tr ' ' '\n' | grep bin").Stdout;
        Configuration.Wireguard.WireguardQuickBin = _systemWrapper
            .RunCommand("whereis wg-quick | tr ' ' '\n' | grep bin").Stdout;
        Configuration.Wireguard.Interfaces = new();
        Configuration.Wireguard.PrimaryDns = new("8.8.8.8", UriKind.RelativeOrAbsolute);
        Configuration.Wireguard.SecondaryDns = new("8.8.4.4", UriKind.RelativeOrAbsolute);
        var publicIp = Network.GetPublicIPAddress();
        Configuration.Wireguard.Endpoint = publicIp == default
            ? default
            : new(publicIp.ToString(), UriKind.RelativeOrAbsolute);
    }

    public abstract void Load();
    public abstract void Save();
    public abstract string Export();
}