using Linguard.Core.Models;
using Linguard.Core.Plugins;

namespace Linguard.Core.Drivers.TrafficStorage; 

public interface ITrafficStorageDriver : IPlugin {
    TimeSpan CollectionInterval { get; set; }
    IDictionary<string, string> AdditionalOptions { get; set; }
    /// <summary>
    /// Store the given traffic data.
    /// </summary>
    /// <param name="data"></param>
    void Save(IEnumerable<ITrafficData> data);
    /// <summary>
    /// Load all the stored traffic data.
    /// </summary>
    /// <returns></returns>
    IEnumerable<ITrafficData> Load();
}