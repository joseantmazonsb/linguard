using YamlDotNet.Serialization;

namespace Linguard.Core.Configuration.Serialization; 

/// <summary>
/// Serializes and deserializes the configuration of the application using YAML.
/// </summary>
public class YamlConfigurationSerializer : IConfigurationSerializer {

    private readonly IDeserializer _deserializer;
    private readonly ISerializer _serializer;
    
    public YamlConfigurationSerializer(ISerializer serializer, IDeserializer deserializer) {
        _serializer = serializer;
        _deserializer = deserializer;
    }
    
    public string Serialize(IConfiguration configuration) {
        return _serializer.Serialize(configuration);
    }

    public IConfiguration Deserialize(string text) {
        return _deserializer.Deserialize<IConfiguration>(text);
    }
}