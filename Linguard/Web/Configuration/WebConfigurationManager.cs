using Linguard.Core.Configuration;
using Linguard.Core.Configuration.Serialization;
using Linguard.Core.OS;
using Linguard.Log;
using Linguard.Yaml;
using IConfiguration = Linguard.Core.Configuration.IConfiguration;

namespace Linguard.Web.Configuration; 

public class WebConfigurationManager : YamlConfigurationManager<IConfiguration>, IConfigurationManager {
    public WebConfigurationManager(IConfiguration configuration, IWorkingDirectory workingDirectory, 
        ISystemWrapper systemWrapper, IConfigurationSerializer serializer, ILinguardLogger logger) 
        : base(configuration, workingDirectory, systemWrapper, serializer, logger) {
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