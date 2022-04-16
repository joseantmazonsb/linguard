using Linguard.Core.Models;
using Linguard.Core.Plugins;

namespace Linguard.Core.Drivers.TrafficStorage; 

public interface ITrafficStorageDriver : IPlugin {
    /// <summary>
    /// Additional settings of the driver. 
    /// </summary>
    /// <remarks>Custom plugins may find this useful.</remarks>
    IDictionary<string, string> AdditionalOptions { get; set; }
    /// <summary>
    /// Determines how frequently should we collect traffic data.
    /// </summary>
    TimeSpan CollectionInterval { get; set; }
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