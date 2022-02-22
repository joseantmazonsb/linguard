using ByteSizeLib;
using Linguard.Core.Models.Wireguard;

namespace Linguard.Core.Models; 

public interface ITrafficData {
    public IWireguardPeer Peer { get; set; }
    ByteSize SentData { get; set; }
    ByteSize ReceivedData { get; set; }
}