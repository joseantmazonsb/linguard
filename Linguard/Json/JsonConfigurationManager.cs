using Linguard.Core.Configuration;
using Linguard.Core.Managers;
using Linguard.Core.OS;
using Linguard.Core.Plugins;

namespace Linguard.Json; 

public class JsonConfigurationManager<T> : FileConfigurationManager<T> where T : IConfiguration {
    public JsonConfigurationManager(IConfiguration configuration, ISystemWrapper systemWrapper, 
        JsonConfigurationSerializer serializer, IPluginEngine pluginEngine) 
        : base(configuration, systemWrapper, serializer, pluginEngine) {
    }
}