using Linguard.Core.OS;
using Linguard.Core.Plugins;
using Linguard.Json;
using Linguard.Web.Configuration.Serialization;

namespace Linguard.Web.Configuration; 

public class WebConfigurationManager : JsonConfigurationManager<IConfiguration>, IConfigurationManager {
    public WebConfigurationManager(IConfiguration configuration, 
        ISystemWrapper systemWrapper, IPluginEngine pluginEngine) 
        : base(configuration, systemWrapper, new JsonConfigurationSerializerWeb(systemWrapper, pluginEngine), 
            pluginEngine) {
    }

    public override void LoadDefaults() {
        var configuration = new WebOptions {
            LoginAttempts = 10,
            LoginBanTime = TimeSpan.FromMinutes(1)
        };
        ((Configuration) Configuration).Web = configuration;
        base.LoadDefaults();
    }
}