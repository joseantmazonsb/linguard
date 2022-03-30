using Linguard.Core.Drivers.TrafficStorage;

namespace Linguard.Core.Configuration; 

public class TrafficConfiguration : ITrafficConfiguration {
    public bool Enabled { get; set; }
    public ITrafficStorageDriver StorageDriver { get; set; }
    public object Clone() {
        var clone = (ITrafficConfiguration) MemberwiseClone();
        clone.StorageDriver = (ITrafficStorageDriver) StorageDriver.Clone();
        return clone;
    }
}