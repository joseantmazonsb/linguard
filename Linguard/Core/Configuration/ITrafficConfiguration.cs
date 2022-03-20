using Linguard.Core.Drivers.TrafficStorage;

namespace Linguard.Core.Configuration; 

public interface ITrafficConfiguration : IConfigurationModule {
    public bool Enabled { get; set; }
    public ITrafficStorageDriver StorageDriver { get; set; }
}