using Linguard.Core.Configuration;
using Linguard.Core.Configuration.Serialization;
using Linguard.Core.OS;

namespace Linguard.Core.Managers; 

public class YamlConfigurationManager : DefaultFileConfigurationManager {

    public override string[] SupportedExtensions => new [] {
        "yaml", "yml"
    };

    public YamlConfigurationManager(IConfiguration configuration, IWorkingDirectory workingDirectory, 
        ICommandRunner commandRunner, IConfigurationSerializer serializer) 
        : base(configuration, workingDirectory, commandRunner, serializer) {
    }
}