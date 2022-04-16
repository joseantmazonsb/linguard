using Linguard.Core.Drivers.TrafficStorage;

namespace Linguard.Core.Configuration; 

public class TrafficOptions : ITrafficOptions {
    public bool Enabled { get; set; }
    public ITrafficStorageDriver StorageDriver { get; set; }
    public object Clone() {
        var clone = (ITrafficOptions) MemberwiseClone();
        clone.StorageDriver = (ITrafficStorageDriver) StorageDriver.Clone();
        return clone;
    }
}