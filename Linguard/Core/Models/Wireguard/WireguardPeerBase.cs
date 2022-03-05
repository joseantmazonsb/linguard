using System.Net.Sockets;

namespace Linguard.Core.Models.Wireguard; 

public abstract class WireguardPeerBase : IWireguardPeer {
    public Guid Id { get; set; }
    public string PublicKey { get; set; }
    public string PrivateKey { get; set; }

    private IPAddressCidr? _ipv6Address;
    private IPAddressCidr? _ipv4Address;
    
    public IPAddressCidr? IPv4Address {
        get => _ipv4Address;
        set {
            if (value != null && value.IPAddress.AddressFamily != AddressFamily.InterNetwork) {
                throw new ArgumentException("This field must be an IPv4 address.");
            }
            _ipv4Address = value;
        } 
    }
    public IPAddressCidr? IPv6Address {
        get => _ipv6Address;
        set {
            if (value != null && value.IPAddress.AddressFamily != AddressFamily.InterNetworkV6) {
                throw new ArgumentException("This field must be an IPv6 address.");
            }
            _ipv6Address = value;
        }
    }

    public string Name { get; set; }
    public string Description { get; set; }
    public abstract string Brief();
    
    protected bool Equals(WireguardPeerBase other) {
        return Id == other.Id;
    }

    public override bool Equals(object? obj) {
        if (ReferenceEquals(null, obj)) return false;
        if (ReferenceEquals(this, obj)) return true;
        return obj.GetType() == GetType() && Equals((WireguardPeerBase)obj);
    }

    public override int GetHashCode() {
        return Id.GetHashCode();
    }
}