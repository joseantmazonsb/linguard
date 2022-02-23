namespace Linguard.Core.Configuration.Exceptions; 

/// <summary>
/// Signals an error while loading the configuration of the application.
/// </summary>
public class ConfigurationNotSavedError : Exception {
    public ConfigurationNotSavedError(string message) : base(message) {}
    public ConfigurationNotSavedError(string message, Exception e) : base(message, e) {}
}