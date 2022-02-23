using Linguard.Core.Models;

namespace Linguard.Core.Drivers.TrafficStorage; 

public interface ITrafficStorageDriver {
    public string TimestampFormat { get; set; }
    public void Save(IEnumerable<ITrafficData> data);
    public IEnumerable<ITrafficData> Load();
}