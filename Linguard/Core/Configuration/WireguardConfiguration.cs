using Linguard.Core.Models.Wireguard;

namespace Linguard.Core.Configuration; 

public class WireguardConfiguration : IWireguardConfiguration {
    public HashSet<Interface> Interfaces { get; set; }
    public string IptablesBin { get; set; }
    public string WireguardBin { get; set; }
    public string WireguardQuickBin { get; set; }
    public Uri? PrimaryDns { get; set; }
    public Uri? SecondaryDns { get; set; }
    public Uri? Endpoint { get; set; }

    public object Clone() {
        return MemberwiseClone();
    }
}