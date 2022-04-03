using Linguard.Core.Configuration;
using Linguard.Core.Configuration.Serialization;
using Linguard.Core.OS;
using Linguard.Core.Plugins;

namespace Linguard.Core.Managers; 

public class YamlConfigurationManager<T> : DefaultFileConfigurationManager<T> where T : IConfiguration {

    public override string[] SupportedExtensions => new [] {
        "yaml", "yml"
    };

    public YamlConfigurationManager(IConfiguration configuration, IWorkingDirectory workingDirectory, 
        ISystemWrapper systemWrapper, IConfigurationSerializer serializer,
        IPluginEngine pluginEngine) 
        : base(configuration, workingDirectory, systemWrapper, serializer, pluginEngine) {
    }
}