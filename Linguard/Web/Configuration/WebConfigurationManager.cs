using Linguard.Core.Configuration;
using Linguard.Core.OS;
using Linguard.Core.Plugins;
using Linguard.Log;
using Linguard.Web.Configuration.Serialization;
using Linguard.Yaml;
using IConfiguration = Linguard.Core.Configuration.IConfiguration;

namespace Linguard.Web.Configuration; 

public class WebConfigurationManager : YamlConfigurationManager<IConfiguration>, IConfigurationManager {
    public WebConfigurationManager(IConfiguration configuration, IWorkingDirectory workingDirectory, 
        ISystemWrapper systemWrapper, ILinguardLogger logger, IPluginEngine pluginEngine) 
        : base(configuration, workingDirectory, systemWrapper, new ConfigurationSerializer(pluginEngine), 
            logger, pluginEngine) {
    }

    public override void LoadDefaults() {
        var configuration = new WebConfiguration {
            LoginAttempts = 10,
            LoginBanTime = TimeSpan.FromMinutes(1)
        };
        Configuration.Modules.Add(configuration);
        base.LoadDefaults();
    }
}