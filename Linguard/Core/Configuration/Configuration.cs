using Linguard.Core.Utils;

namespace Linguard.Core.Configuration; 

public class Configuration : IConfiguration {
    public IWireguardConfiguration Wireguard { get; set; } = new WireguardConfiguration();
    public ILoggingConfiguration Logging { get; set; } = new LoggingConfiguration();
    public IWebConfiguration Web { get; set; } = new WebConfiguration();
    public ITrafficConfiguration Traffic { get; set; } = new TrafficConfiguration();
    
    public object Clone() {
        return Cloning.Clone(this);
    }
}