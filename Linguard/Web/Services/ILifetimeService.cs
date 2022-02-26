namespace Linguard.Web.Services; 

public interface ILifetimeService {
    void OnAppStarted();
    void OnAppStopping();
    void OnAppStopped();
}