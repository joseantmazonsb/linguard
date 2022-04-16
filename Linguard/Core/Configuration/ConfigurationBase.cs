using Linguard.Core.Utils;

namespace Linguard.Core.Configuration; 

public class ConfigurationBase : IConfiguration {
    public IWireguardOptions Wireguard { get; set; }
    public ITrafficOptions Traffic { get; set; }
    public IPluginOptions Plugins { get; set; }
    public IAuthenticationOptions Authentication { get; set; }

    public object Clone() {
        return Cloning.Clone(this);
    }
}