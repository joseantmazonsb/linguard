namespace Linguard.Core.Configuration; 

/// <summary>
/// Represents all configurable settings.
/// </summary>
public interface IConfiguration : ICloneable {
    T? GetModule<T>() where T : IConfigurationModule;
    ISet<IConfigurationModule> Modules { get; set; }
}