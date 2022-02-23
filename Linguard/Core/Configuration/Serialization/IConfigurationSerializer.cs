namespace Linguard.Core.Configuration.Serialization; 

/// <summary>
/// Represents a class capable of serializing and deserializing the configuration of the application.
/// </summary>
public interface IConfigurationSerializer {
    string Serialize(IConfiguration configuration);
    IConfiguration Deserialize(string text);
}