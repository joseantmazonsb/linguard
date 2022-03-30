using ByteSizeLib;
using Linguard.Core.Models.Wireguard;

namespace Linguard.Core.Models; 

public class TrafficData : ITrafficData {
    public IWireguardPeer Peer { get; set; }
    public ByteSize SentData { get; set; }
    public ByteSize ReceivedData { get; set; }
    public DateTime TimeStamp { get; set; }

    protected bool Equals(TrafficData other) {
        return Peer.Equals(other.Peer) && SentData.Equals(other.SentData) && ReceivedData.Equals(other.ReceivedData) && TimeStamp.Equals(other.TimeStamp);
    }

    public override bool Equals(object? obj) {
        if (ReferenceEquals(null, obj)) return false;
        if (ReferenceEquals(this, obj)) return true;
        if (obj.GetType() != this.GetType()) return false;
        return Equals((TrafficData)obj);
    }

    public override int GetHashCode() {
        return HashCode.Combine(Peer, SentData, ReceivedData, TimeStamp);
    }
}