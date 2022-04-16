using Linguard.Core.Models.Wireguard;

namespace Linguard.Core.Configuration; 

public interface IWireguardOptions : IOptionsModule {
    DirectoryInfo InterfacesDirectory { get; set; }
    ISet<Interface> Interfaces { get; set; }
    /// <summary>
    /// Path to the <c>iptables</c> binary file.
    /// </summary>
    string IptablesBin { get; set; }
    /// <summary>
    /// Path to the <c>wg</c> binary file.
    /// </summary>
    string WireguardBin { get; set; }
    /// <summary>
    /// Path to the <c>wg-quick</c> binary file.
    /// </summary>
    string WireguardQuickBin { get; set; }
    /// <summary>
    /// Default primary DNS for all peers if none specified at interface level.  
    /// </summary>
    Uri? PrimaryDns { get; set; }
    /// <summary>
    /// Default secondary DNS for all peers if none specified at interface level.  
    /// </summary>
    Uri? SecondaryDns { get; set; }
    /// <summary>
    /// Default endpoint for all peers if none specified at interface level.  
    /// </summary>
    Uri? Endpoint { get; set; }
    /// <summary>
    /// Get the interface associated to the given client or <c>default</c> if none found.
    /// </summary>
    /// <param name="client"></param>
    /// <returns></returns>
    Interface? GetInterface(Client client);

    /// <summary>
    /// Get the interface associated to the client whose public key is <c>publicKey</c> or <c>default</c> if none found.
    /// </summary>
    /// <param name="publicKey"></param>
    /// <returns></returns>
    Interface? GetInterface(string publicKey);
    FileInfo GetInterfaceConfigurationFile(Interface @interface);
}