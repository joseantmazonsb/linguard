﻿using System.Net;
using Linguard.Core.Configuration;
using Linguard.Core.Configuration.Serialization;
using Linguard.Core.Drivers.TrafficStorage;
using Linguard.Core.Models;
using Linguard.Core.Models.Wireguard;
using Linguard.Core.OS;
using Linguard.Core.Utils;
using Linguard.Log;

namespace Linguard.Core.Managers; 

public class YamlConfigurationManager : FileConfigurationManager {
    private static readonly string[] SupportedExtensions = {"yaml", "yml"};

    private FileInfo? _configurationFile;
    private readonly ICommandRunner _commandRunner;

    protected sealed override FileInfo ConfigurationFile {
        get {
            if (_configurationFile != default) return _configurationFile;
            var filename = Path.Combine(WorkingDirectory.BaseDirectory.FullName, AssemblyInfo.Product.ToLower());
            var tries = 0;
            while (tries < SupportedExtensions.Length && _configurationFile is not { Exists: true }) {
                var filepath = Path.ChangeExtension(filename, SupportedExtensions[tries]);
                _configurationFile = new FileInfo(filepath);
                tries++;
            }
            return _configurationFile!;
        }
    }

    public override void LoadDefaults() {
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
        Configuration.Wireguard.IptablesBin = _commandRunner
            .Run("whereis iptables | tr ' ' '\n' | grep bin").Stdout;
        Configuration.Wireguard.WireguardBin = _commandRunner
            .Run("whereis wg | tr ' ' '\n' | grep bin").Stdout;
        Configuration.Wireguard.WireguardQuickBin = _commandRunner
            .Run("whereis wg-quick | tr ' ' '\n' | grep bin").Stdout;
        Configuration.Wireguard.Interfaces = new();
        Configuration.Wireguard.PrimaryDns = new("8.8.8.8", UriKind.RelativeOrAbsolute);
        Configuration.Wireguard.SecondaryDns = new("8.8.4.4", UriKind.RelativeOrAbsolute);
        var publicIp = Network.GetPublicIPAddress();
        Configuration.Wireguard.Endpoint = publicIp == default
            ? default
            : new(publicIp.ToString(), UriKind.RelativeOrAbsolute);
    }

    public YamlConfigurationManager(IConfiguration configuration, IWorkingDirectory workingDirectory, 
        IConfigurationSerializer serializer, ICommandRunner commandRunner) 
        : base(configuration, workingDirectory, serializer) {
        _commandRunner = commandRunner;
    }
}