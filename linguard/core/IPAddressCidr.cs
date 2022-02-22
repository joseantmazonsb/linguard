using System.Net;
using System.Net.Sockets;

namespace Linguard.Core; 

public class IPAddressCidr {
    public IPAddress IPAddress { get; set; }
    public byte Cidr { get; set; }
    
    public IPNetwork IPNetwork => IPNetwork.Parse(IPAddress, Cidr);

    public override string ToString() {
        return $"{IPAddress}/{Cidr}";
    }

    public bool Contains(IPAddressCidr address) {
        return IPNetwork.Contains(address.IPAddress);
    }
    
    public bool Contains(IPAddress address) {
        return IPNetwork.Contains(address);
    }
    
    protected bool Equals(IPAddressCidr other) {
        return IPAddress.Equals(other.IPAddress) && Cidr == other.Cidr;
    }

    public override bool Equals(object? obj) {
        if (ReferenceEquals(null, obj)) return false;
        if (ReferenceEquals(this, obj)) return true;
        if (obj.GetType() != this.GetType()) return false;
        return Equals((IPAddressCidr)obj);
    }

    public override int GetHashCode() {
        return HashCode.Combine(IPAddress, Cidr);
    }

    public static IPAddressCidr Parse(string address) {
        var split = address.Split("/", 2);
        try {
            var ip = IPAddress.Parse(split[0]);
            var cidr = byte.Parse(split[1]);
            AssertRightCidr(ip, cidr);
            return new IPAddressCidr {
                IPAddress = ip,
                Cidr = cidr
            };
        }
        catch {
            throw new ArgumentException($"Invalid IP address with cidr mask: '{address}'");
        }
    }
    
    public static IPAddressCidr Parse(IPAddress address, byte cidr) {
        AssertRightCidr(address, cidr);
        return new IPAddressCidr {
            IPAddress = address,
            Cidr = cidr
        };
    }

    private static void AssertRightCidr(IPAddress address, byte cidr) {
        if (cidr < 0) throw new Exception($"Invalid Cidr: {cidr}");
        if (address.AddressFamily == AddressFamily.InterNetwork && cidr > 32) {
            throw new Exception();
        }
        if (address.AddressFamily == AddressFamily.InterNetworkV6 && cidr > 64) {
            throw new Exception();
        }
    }
}