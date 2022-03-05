using System.Net.NetworkInformation;

namespace Linguard.Core.Models.Wireguard; 

public class Interface : WireguardPeerBase, ICloneable {
    public NetworkInterface Gateway { get; set; }
    public int Port { get; set; }
    public bool Auto { get; set; }
    public ISet<Client> Clients { get; set; }
    public ISet<Rule> OnUp { get; set; }
    public ISet<Rule> OnDown { get; set; }
    /// <summary>
    /// Default primary DNS for all peers if none specified.  
    /// </summary>
    public Uri? PrimaryDns { get; set; }
    /// <summary>
    /// Default secondary DNS for all peers if none specified.  
    /// </summary>
    public Uri? SecondaryDns { get; set; }
    /// <summary>
    /// Default endpoint for all peers if none specified.  
    /// </summary>
    public Uri? Endpoint { get; set; }

    public override string ToString() {
        return $"Name: {Name}{Environment.NewLine}" +
               $"Description: {Description}{Environment.NewLine}" +
               $"IPv4: {IPv4Address}{Environment.NewLine}" +
               $"IPv6: {IPv6Address}{Environment.NewLine}" +
               $"Port: {Port}{Environment.NewLine}" +
               $"Gateway: {Gateway.Name}{Environment.NewLine}" +
               $"Auto: {Auto}{Environment.NewLine}" +
               $"Clients: {Clients.Count}{Environment.NewLine}" +
               $"Public key: {PublicKey}{Environment.NewLine}" +
               $"Private key: {PrivateKey}{Environment.NewLine}" +
               $"OnUp: {string.Join("; ", OnUp)}{Environment.NewLine}" +
               $"OnDown: {string.Join("; ", OnDown)}{Environment.NewLine}" +
               $"Endpoint: {Endpoint}{Environment.NewLine}" +
               $"Primary DNS: {PrimaryDns}{Environment.NewLine}" +
               $"Secondary DNS: {SecondaryDns}";
    }

    public object Clone() {
        return MemberwiseClone();
    }

    public override string Brief() {
        return $"Name: {Name}, " +
               $"Port: {Port}, " +
               $"Gateway: {Gateway.Name}, " +
               $"IPv4: {IPv4Address}, " +
               $"IPv6: {IPv6Address}, " +
               $"Auto: {Auto}, " +
               $"Clients: {Clients.Count}";
    }
}