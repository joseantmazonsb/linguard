﻿using Linguard.Core.Configuration;
using Linguard.Core.Drivers.TrafficStorage;
using Linguard.Core.Models.Wireguard;
using Linguard.Core.OS;
using Linguard.Core.Utils;
using Linguard.Log;
using Microsoft.Extensions.Logging;

namespace Linguard.Core.Managers; 

public abstract class ConfigurationManagerBase : IConfigurationManager {
    
    private readonly ISystemWrapper _systemWrapper;
    private readonly ILinguardLogger _logger;

    protected ConfigurationManagerBase(IConfiguration configuration, IWorkingDirectory workingDirectory, 
        ISystemWrapper systemWrapper, ILinguardLogger logger) {
        Configuration = configuration;
        WorkingDirectory = workingDirectory;
        _systemWrapper = systemWrapper;
        _logger = logger;
    }
    
    public IConfiguration Configuration { get; set; }
    public IWorkingDirectory WorkingDirectory { get; set; }
    public bool IsSetupNeeded { get; set; } = true;

    public void LoadDefaults() {
        LoadWebDefaults();
        LoadLoggingDefaults();
        LoadTrafficDefaults();
        LoadWireguardDefaults();
    }

    private void LoadWebDefaults() {
        Configuration.Web = new WebConfiguration();
        Configuration.Web.LoginAttempts = 10;
        Configuration.Web.SecretKey = "";
    }
    private void LoadLoggingDefaults() {
        Configuration.Logging = new LoggingConfiguration();
        Configuration.Logging.Level = LogLevel.Information;
        Configuration.Logging.DateTimeFormat = _logger.DateTimeFormat;
    }
    private void LoadTrafficDefaults() {
        Configuration.Traffic = new TrafficConfiguration();
        Configuration.Traffic.Enabled = true;
        Configuration.Traffic.StorageDriver = new JsonTrafficStorageDriver();
    }
    private void LoadWireguardDefaults() {
        Configuration.Wireguard = new WireguardConfiguration();
        Configuration.Wireguard.Interfaces = new HashSet<Interface>();
        Configuration.Wireguard.Interfaces = new HashSet<Interface>();
        Configuration.Wireguard.PrimaryDns = new("8.8.8.8", UriKind.RelativeOrAbsolute);
        Configuration.Wireguard.SecondaryDns = new("8.8.4.4", UriKind.RelativeOrAbsolute);
        var publicIp = Network.GetPublicIPAddress();
        Configuration.Wireguard.Endpoint = publicIp == default
            ? default
            : new(publicIp.ToString(), UriKind.RelativeOrAbsolute);
        Configuration.Wireguard.IptablesBin = _systemWrapper
            .RunCommand("whereis iptables | tr ' ' '\n' | grep bin").Stdout;
        Configuration.Wireguard.WireguardBin = _systemWrapper
            .RunCommand("whereis wg | tr ' ' '\n' | grep bin").Stdout;
        Configuration.Wireguard.WireguardQuickBin = _systemWrapper
            .RunCommand("whereis wg-quick | tr ' ' '\n' | grep bin").Stdout;
    }

    public abstract void Load();

    public void Save() {
        IsSetupNeeded = false;
        ApplyChanges();
        DoSave();
    }

    private void ApplyChanges() {
        ApplyLogChanges();

        void ApplyLogChanges() {
            _logger.LogLevel = Configuration.Logging.Level;
            _logger.DateTimeFormat = Configuration.Logging.DateTimeFormat;
        }
    }

    protected abstract void DoSave();
    public abstract string Export();
}