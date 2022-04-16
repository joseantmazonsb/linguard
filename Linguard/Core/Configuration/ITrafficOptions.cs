using Linguard.Core.Drivers.TrafficStorage;

namespace Linguard.Core.Configuration; 

public interface ITrafficOptions : IOptionsModule {
    /// <summary>
    /// Whether traffic data collection will be performed or not.
    /// </summary>
    bool Enabled { get; set; }
    /// <summary>
    /// Driver that handles traffic data collection.
    /// </summary>
    ITrafficStorageDriver StorageDriver { get; set; }
}