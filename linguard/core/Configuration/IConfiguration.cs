namespace Linguard.Core.Configuration; 

/// <summary>
/// Represents all configurable settings.
/// </summary>
public interface IConfiguration : ICloneable {
    /// <summary>
    /// Wireguard related settings.
    /// </summary>
    IWireguardConfiguration Wireguard { get; set; }
    /// <summary>
    /// Logging related settings.
    /// </summary>
    ILoggingConfiguration Logging { get; set; }
    /// <summary>
    /// Web related settings.
    /// </summary>
    IWebConfiguration Web { get; set; }
    /// <summary>
    /// Traffic related settings.
    /// </summary>
    ITrafficConfiguration Traffic { get; set; }
}