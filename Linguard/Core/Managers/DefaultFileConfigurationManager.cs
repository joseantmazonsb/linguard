﻿using Linguard.Core.Configuration;
using Linguard.Core.Configuration.Serialization;
using Linguard.Core.OS;
using Linguard.Core.Plugins;
using Linguard.Core.Utils;
using Linguard.Log;

namespace Linguard.Core.Managers; 

public abstract class DefaultFileConfigurationManager<T> : FileConfigurationManager<T> where T : IConfiguration {
    
    protected DefaultFileConfigurationManager(IConfiguration configuration, IWorkingDirectory workingDirectory, 
        ISystemWrapper systemWrapper, IConfigurationSerializer serializer, ILinguardLogger logger, 
        IPluginEngine pluginEngine) 
        : base(configuration, workingDirectory, systemWrapper, serializer, logger, pluginEngine) {
    }

    private FileInfo? _configurationFile;
    
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
}