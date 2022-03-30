namespace Linguard.Web.Services; 

public interface ILifetimeService {
    Task OnAppStarted();
    Task OnAppStopping();
    Task OnAppStopped();
}