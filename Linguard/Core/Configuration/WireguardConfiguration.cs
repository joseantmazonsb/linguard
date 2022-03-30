using Linguard.Core.Models.Wireguard;

namespace Linguard.Core.Configuration; 

public class WireguardConfiguration : IWireguardConfiguration {
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
        return MemberwiseClone();
    }
}