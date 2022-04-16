using Linguard.Core.Models.Wireguard;

namespace Linguard.Core.Configuration; 

public class WireguardOptions : IWireguardOptions {
    private const string WireguardConfigurationFileExtension = "conf";
    public DirectoryInfo InterfacesDirectory { get; set; }
    public ISet<Interface> Interfaces { get; set; }
    public string IptablesBin { get; set; }
    public string WireguardBin { get; set; }
    public string WireguardQuickBin { get; set; }
    public Uri? PrimaryDns { get; set; }
    public Uri? SecondaryDns { get; set; }
    public Uri? Endpoint { get; set; }
    public Interface? GetInterface(Client client) => Interfaces
        .SingleOrDefault(i => i.Clients.Contains(client));

    public Interface? GetInterface(string publicKey) => Interfaces
        .SingleOrDefault(i => i.Clients.Any(c => c.PublicKey == publicKey));

    public object Clone() {
        var clone = (IWireguardOptions) MemberwiseClone();
        clone.Interfaces = new HashSet<Interface>(Interfaces);
        return clone;
    }
    public FileInfo GetInterfaceConfigurationFile(Interface @interface) =>
        new(Path.ChangeExtension(Path.Combine(InterfacesDirectory.FullName, @interface.Name), 
            WireguardConfigurationFileExtension));
}