namespace Linguard.Core.Configuration.Serialization; 

/// <summary>
/// Represents a class capable of serializing and deserializing the configuration of the application.
/// </summary>
public interface IConfigurationSerializer {
    string Serialize<T>(T configuration) where T : IConfiguration;
    T Deserialize<T>(string text) where T : IConfiguration;
}