using Linguard.Core.Models.Wireguard;

namespace Linguard.Core.Services; 

public interface IWireguardConfigParser {
    T Parse<T>(string config) where T : IWireguardPeer;
    Interface Parse(string config, IEnumerable<string> clientsConfig);
}