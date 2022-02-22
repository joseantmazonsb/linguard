using Linguard.Core.Configuration;
using Linguard.Core.Configuration.Exceptions;
using Linguard.Core.Configuration.Serialization;

namespace Linguard.Core.Managers; 

public abstract class FileConfigurationManager : IConfigurationManager {
    
    protected FileConfigurationManager(IConfiguration configuration, IWorkingDirectory workingDirectory, 
        IConfigurationSerializer serializer) {
        Configuration = configuration;
        WorkingDirectory = workingDirectory;
        Serializer = serializer;
    }

    public IConfiguration Configuration { get; set; }
    public IWorkingDirectory WorkingDirectory { get; set; }
    protected abstract FileInfo ConfigurationFile { get; }
    private IConfigurationSerializer Serializer { get; }

    public abstract void LoadDefaults();

    public void Load() {
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

    public void Save() {
        try {
            File.WriteAllText(ConfigurationFile.FullName, Export());
        }
        catch (Exception e) {
            throw new ConfigurationNotSavedError(
                $"Unable to save configuration to '{ConfigurationFile.FullName}'", e
            );
        }
    }

    public string Export() {
        return Serializer.Serialize(Configuration);
    }
}