using Linguard.Core.Drivers.TrafficStorage;

namespace Linguard.Core.Configuration; 

public class TrafficConfiguration : ITrafficConfiguration {
    public bool Enabled { get; set; }
    public ITrafficStorageDriver StorageDriver { get; set; }
    public object Clone() {
        return MemberwiseClone();
    }
}