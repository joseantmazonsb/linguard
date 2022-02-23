using System.Net.NetworkInformation;

namespace Linguard.Core.Utils.Comparers; 

public class NetworkInterfaceNameComparer : IEqualityComparer<NetworkInterface> {
    public bool Equals(NetworkInterface? x, NetworkInterface? y) {
        if (ReferenceEquals(x, y)) return true;
        if (ReferenceEquals(x, null)) return false;
        if (ReferenceEquals(y, null)) return false;
        if (x.GetType() != y.GetType()) return false;
        return x.Name == y.Name;
    }

    public int GetHashCode(NetworkInterface obj) {
        return obj.Name.GetHashCode();
    }
}