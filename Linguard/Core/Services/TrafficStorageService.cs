using Linguard.Core.Configuration;
using Linguard.Core.Drivers.TrafficStorage;
using Linguard.Core.Managers;
using Linguard.Core.Models;
using Timer = System.Timers.Timer;

namespace Linguard.Core.Services;

public class TrafficStorageService : ITrafficStorageService {
    private ITrafficConfiguration Configuration => _configurationManager.Configuration.GetModule<ITrafficConfiguration>()!;
    private readonly IConfigurationManager _configurationManager;
    private readonly IWireguardService _wireguardService;
    private readonly Timer _timer;
    
    public TrafficStorageService(IConfigurationManager configurationManager, 
        IWireguardService wireguardService) {
        _configurationManager = configurationManager;
        _wireguardService = wireguardService;
        _timer = new Timer {
            Enabled = false,
            AutoReset = true,
            Interval = Configuration.StorageDriver.CollectionInterval.TotalMilliseconds
        };
        _timer.Elapsed += (_, _) => {
            CollectData();
        };
    }
    private void CollectData() {
        var data = _wireguardService.GetTrafficData();
        Configuration.StorageDriver.Save(data);
    }
    
    public void RefreshConfiguration() {
        _timer.Enabled = Configuration.Enabled;
        _timer.Interval = Configuration.StorageDriver.CollectionInterval.TotalMilliseconds;
    }

    public IEnumerable<ITrafficData> LoadData() {
        return Configuration.StorageDriver.Load();
    }
}