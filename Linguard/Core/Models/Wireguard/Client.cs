namespace Linguard.Core.Models.Wireguard; 

public class Client : WireguardPeerBase, ICloneable {
    public ISet<IPAddressCidr> AllowedIPs { get; set; }
    public bool Nat { get; set; }
    public Uri PrimaryDns { get; set; }
    public Uri? SecondaryDns { get; set; }
    public Uri Endpoint { get; set; }

    public override string Brief() {
        return $"Name: {Name}, " +
               $"Endpoint: {Endpoint}, " +
               $"IPv4: {IPv4Address}, " +
               $"IPv6: {IPv6Address}, " +
               $"Nat: {Nat}";
    }

    public override string ToString() {
        return $"Name: {Name}{Environment.NewLine}" +
               $"Description: {Description}{Environment.NewLine}" +
               $"Endpoint: {Endpoint}{Environment.NewLine}" +
               $"IPv4: {IPv4Address}{Environment.NewLine}" +
               $"IPv6: {IPv6Address}{Environment.NewLine}" +
               $"Primary DNS: {PrimaryDns}{Environment.NewLine}" +
               $"Secondary DNS: {SecondaryDns}{Environment.NewLine}" +
               $"Nat: {Nat}{Environment.NewLine}" +
               $"Private key: {PrivateKey}{Environment.NewLine}" +
               $"Public key: {PublicKey}{Environment.NewLine}" +
               $"AllowedIPs: {string.Join(", ", AllowedIPs.Select(ip => ip.ToString()))}";
    }

    public object Clone() {
        return MemberwiseClone();
    }
}
