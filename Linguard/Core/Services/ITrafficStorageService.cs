using Linguard.Core.Models;

namespace Linguard.Core.Services; 

public interface ITrafficStorageService {
    void RefreshConfiguration();
    IEnumerable<ITrafficData> LoadData();
}