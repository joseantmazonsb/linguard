using Linguard.Core.Managers;
using Linguard.Core.Models;

namespace Linguard.Core.Drivers.TrafficStorage; 

public abstract class TrafficStorageDriverBase : ITrafficStorageDriver {
    public abstract string Name { get; }
    public abstract string Description { get; }
    public virtual TimeSpan CollectionInterval { get; set; } = TimeSpan.FromHours(1);
    public IDictionary<string, string> AdditionalOptions { get; set; } = new Dictionary<string, string>();
    protected IConfigurationManager? ConfigurationManager { get; private set; }
    
    public void Initialize(IConfigurationManager configurationManager) {
        ConfigurationManager = configurationManager;
    }
    public abstract void Save(IEnumerable<ITrafficData> data);
    public abstract IEnumerable<ITrafficData> Load();
    public abstract object Clone();
}