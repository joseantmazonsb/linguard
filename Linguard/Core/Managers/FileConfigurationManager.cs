using Linguard.Core.Configuration;
using Linguard.Core.Configuration.Exceptions;
using Linguard.Core.Configuration.Serialization;
using Linguard.Core.OS;

namespace Linguard.Core.Managers; 

public abstract class FileConfigurationManager : ConfigurationManagerBase {
    
    protected FileConfigurationManager(IConfiguration configuration, IWorkingDirectory workingDirectory, 
        ISystemWrapper systemWrapper, IConfigurationSerializer serializer) : base(configuration, workingDirectory, systemWrapper) {
        Configuration = configuration;
        WorkingDirectory = workingDirectory;
        Serializer = serializer;
    }

    protected abstract FileInfo ConfigurationFile { get; }
    private IConfigurationSerializer Serializer { get; }

    public abstract string[] SupportedExtensions { get; }
    
    public override void Load() {
        if (!ConfigurationFile.Exists) {
            throw new ConfigurationNotLoadedError(
                $"Configuration file '{ConfigurationFile.FullName}' does not exist."
            );
        }

        try {
            Configuration = Serializer.Deserialize(File.ReadAllText(ConfigurationFile.FullName));
        }
        catch (Exception e) {
            throw new ConfigurationNotLoadedError(
                $"Unable to load configuration from '{ConfigurationFile.FullName}'", e
            );
        }
    }
    public override void Save() {
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