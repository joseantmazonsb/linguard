namespace Linguard.Core.Configuration.Exceptions; 

/// <summary>
/// Signals an error while loading the configuration of the application.
/// </summary>
public class ConfigurationNotLoadedError : Exception {
    public ConfigurationNotLoadedError(string message) : base(message) {}
    public ConfigurationNotLoadedError(string message, Exception e) : base(message, e) {}
}