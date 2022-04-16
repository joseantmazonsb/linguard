using Linguard.Core.Configuration;
using Linguard.Core.Drivers.TrafficStorage;
using Linguard.Core.Managers;
using Linguard.Core.Models;
using Timer = System.Timers.Timer;

namespace Linguard.Core.Services;

public class TrafficStorageService : ITrafficStorageService {
    private ITrafficOptions Options => _configurationManager.Configuration.Traffic;
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
            Interval = Options.StorageDriver.CollectionInterval.TotalMilliseconds
        };
        _timer.Elapsed += (_, _) => {
            CollectData();
        };
    }
    private void CollectData() {
        var data = _wireguardService.GetTrafficData();
        Options.StorageDriver.Save(data);
    }
    
    public void RefreshConfiguration() {
        _timer.Enabled = Options.Enabled;
        _timer.Interval = Options.StorageDriver.CollectionInterval.TotalMilliseconds;
    }

    public IEnumerable<ITrafficData> LoadData() {
        return Options.StorageDriver.Load();
    }
}