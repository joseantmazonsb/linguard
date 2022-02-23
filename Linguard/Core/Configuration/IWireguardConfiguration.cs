using Linguard.Core.Models.Wireguard;

namespace Linguard.Core.Configuration; 

public interface IWireguardConfiguration : ICloneable {
    public HashSet<Interface> Interfaces { get; set; }
    /// <summary>
    /// Path to the <c>iptables</c> binary file.
    /// </summary>
    public string IptablesBin { get; set; }
    /// <summary>
    /// Path to the <c>wg</c> binary file.
    /// </summary>
    public string WireguardBin { get; set; }
    /// <summary>
    /// Path to the <c>wg-quick</c> binary file.
    /// </summary>
    public string WireguardQuickBin { get; set; }
    /// <summary>
    /// Default primary DNS for all peers if none specified at interface level.  
    /// </summary>
    public Uri? PrimaryDns { get; set; }
    /// <summary>
    /// Default secondary DNS for all peers if none specified at interface level.  
    /// </summary>
    public Uri? SecondaryDns { get; set; }
    /// <summary>
    /// Default endpoint for all peers if none specified at interface level.  
    /// </summary>
    public Uri? Endpoint { get; set; }
}