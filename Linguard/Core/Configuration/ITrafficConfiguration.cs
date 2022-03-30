using Linguard.Core.Drivers.TrafficStorage;

namespace Linguard.Core.Configuration; 

public interface ITrafficConfiguration : IConfigurationModule {
    bool Enabled { get; set; }
    ITrafficStorageDriver StorageDriver { get; set; }
}