using ByteSizeLib;
using Linguard.Core.Models.Wireguard;

namespace Linguard.Core.Models; 

public class TrafficData : ITrafficData {
    public IWireguardPeer Peer { get; set; }
    public ByteSize SentData { get; set; }
    public ByteSize ReceivedData { get; set; }
}