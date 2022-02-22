using Linguard.Core.Drivers.TrafficStorage;

namespace Linguard.Core.Configuration; 

public class TrafficConfiguration : ITrafficConfiguration {
    public bool Enabled { get; set; } = true;
    public ITrafficStorageDriver StorageDriver { get; set; } = new JsonTrafficStorageDriver();
    public object Clone() {
        return MemberwiseClone();
    }
}