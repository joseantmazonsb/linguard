namespace Linguard.Core.Models.Wireguard; 

public interface IWireguardPeer {
    public Guid Id { get; set; }
    public string PrivateKey { get; set; }
    public string PublicKey { get; set; }
    public IPAddressCidr? IPv4Address { get; set; }
    public IPAddressCidr? IPv6Address { get; set; }
    public string Name { get; set; }
    public string Description { get; set; }
    public string Brief();
}