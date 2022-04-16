namespace Linguard.Core.Configuration; 

/// <summary>
/// Represents all configurable settings.
/// </summary>
public interface IConfiguration : ICloneable {
    IWireguardOptions Wireguard { get; set; }
    ITrafficOptions Traffic { get; set; }
    IPluginOptions Plugins { get; set; }
    IAuthenticationOptions Authentication { get; set; }

}