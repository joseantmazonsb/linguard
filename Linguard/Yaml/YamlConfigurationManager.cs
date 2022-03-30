﻿using Linguard.Core.Configuration;
using Linguard.Core.Configuration.Serialization;
using Linguard.Core.Managers;
using Linguard.Core.OS;
using Linguard.Core.Plugins;
using Linguard.Log;

namespace Linguard.Yaml; 

public class YamlConfigurationManager<T> : DefaultFileConfigurationManager<T> where T : IConfiguration {

    public override string[] SupportedExtensions => new [] {
        "yaml", "yml"
    };

    public YamlConfigurationManager(IConfiguration configuration, IWorkingDirectory workingDirectory, 
        ISystemWrapper systemWrapper, IConfigurationSerializer serializer, ILinguardLogger logger, 
        IPluginEngine pluginEngine) 
        : base(configuration, workingDirectory, systemWrapper, serializer, logger, pluginEngine) {
    }
}