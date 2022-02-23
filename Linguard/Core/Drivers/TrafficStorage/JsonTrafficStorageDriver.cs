using Linguard.Core.Models;

namespace Linguard.Core.Drivers.TrafficStorage;

public class JsonTrafficStorageDriver : ITrafficStorageDriver {
    public string TimestampFormat { get; set; }
    
    public void Save(IEnumerable<ITrafficData> data) {
        throw new NotImplementedException();
    }

    public IEnumerable<ITrafficData> Load() {
        throw new NotImplementedException();
    }
}