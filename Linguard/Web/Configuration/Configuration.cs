using Linguard.Core.Configuration;
using Linguard.Core.Utils;

namespace Linguard.Web.Configuration; 

public class Configuration : IConfiguration {
    public IWireguardOptions Wireguard { get; set; }
    public ITrafficOptions Traffic { get; set; }
    public IPluginOptions Plugins { get; set; }
    public IAuthenticationOptions Authentication { get; set; }
    public IWebOptions Web { get; set; }
    
    public object Clone() {
        return Cloning.Clone(this);
    }
}
