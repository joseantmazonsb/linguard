using Linguard.Core.Models.Wireguard;

namespace Linguard.Core.Services; 

public interface IInterfaceGenerator {
    /// <summary>
    /// Create a valid interface.
    /// </summary>
    /// <returns></returns>
    Interface Generate();
}