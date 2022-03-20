using Linguard.Core.Configuration;
using Linguard.Core.Configuration.Serialization;
using Linguard.Core.OS;
using Linguard.Log;

namespace Linguard.Core.Managers; 

public class YamlConfigurationManager<T> : DefaultFileConfigurationManager<T> where T : IConfiguration {

    public override string[] SupportedExtensions => new [] {
        "yaml", "yml"
    };

    public YamlConfigurationManager(IConfiguration configuration, IWorkingDirectory workingDirectory, 
        ISystemWrapper systemWrapper, IConfigurationSerializer serializer, ILinguardLogger logger) 
        : base(configuration, workingDirectory, systemWrapper, serializer, logger) {
    }
}