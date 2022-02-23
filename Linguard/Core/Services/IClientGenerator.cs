using Linguard.Core.Models.Wireguard;

namespace Linguard.Core.Services; 

public interface IClientGenerator {
    /// <summary>
    /// Create a valid peer for the given interface
    /// </summary>
    /// <param name="iface"></param>
    /// <returns></returns>
    Client Generate(Interface iface);
}