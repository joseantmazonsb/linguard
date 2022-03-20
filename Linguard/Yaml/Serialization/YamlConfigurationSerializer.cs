using Linguard.Core.Configuration;
using Linguard.Core.Configuration.Serialization;
using YamlDotNet.Serialization;

namespace Linguard.Yaml.Serialization; 

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
    
    public string Serialize<T>(T configuration) where T : IConfiguration {
        return _serializer.Serialize(configuration);
    }

    public T Deserialize<T>(string text) where T : IConfiguration {
        return _deserializer.Deserialize<T>(text);
    }
}