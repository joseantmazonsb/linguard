using Linguard.Core.Configuration;
using Linguard.Core.Configuration.Exceptions;
using Linguard.Core.Configuration.Serialization;
using Linguard.Core.OS;
using Linguard.Core.Plugins;

namespace Linguard.Core.Managers; 

public abstract class FileConfigurationManager<T> : ConfigurationManagerBase where T : IConfiguration {
    
    protected FileConfigurationManager(IConfiguration configuration, 
        ISystemWrapper systemWrapper, IConfigurationSerializer serializer, 
        IPluginEngine pluginEngine) 
        : base(configuration, systemWrapper, pluginEngine) {
        Configuration = configuration;
        Serializer = serializer;
    }

    private FileInfo ConfigurationFile => new(ConfigurationSource);
    private IConfigurationSerializer Serializer { get; }

    public override void Load() {
        if (!ConfigurationFile.Exists) {
            throw new ConfigurationNotLoadedError(
                $"Configuration file '{ConfigurationFile.FullName}' does not exist."
            );
        }
        try {
            var text = File.ReadAllText(ConfigurationFile.FullName);
            Configuration = Serializer.Deserialize<T>(text);
        }
        catch (Exception e) {
            throw new ConfigurationNotLoadedError(
                $"Unable to load configuration from '{ConfigurationFile.FullName}'", e
            );
        }
    }

    protected override void DoSave() {
        try {
            File.WriteAllText(ConfigurationFile.FullName, Export());
        }
        catch (Exception e) {
            throw new ConfigurationNotSavedError(
                $"Unable to save configuration to '{ConfigurationFile.FullName}'", e
            );
        }
    }
    public override string Export() {
        return Serializer.Serialize(Configuration);
    }
}