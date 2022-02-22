using Linguard.Core.Drivers.TrafficStorage;
using YamlDotNet.Core;
using YamlDotNet.Serialization;
using YamlDotNet.Serialization.NamingConventions;

namespace Linguard.Core.Configuration.Serialization; 

/// <summary>
/// Serializes and deserializes the configuration of the application using YAML.
/// </summary>
public class YamlConfigurationSerializer : IConfigurationSerializer {

    private readonly IDeserializer _deserializer;
    private readonly ISerializer _serializer;
    
    public YamlConfigurationSerializer() {
        var namingConvention = PascalCaseNamingConvention.Instance;
        var ipAddressCidrTypeConverter = new IPAddressCidrTypeConverter();
        var networkInterfaceTypeConverter = new NetworkInterfaceTypeConverter();
        var styleTypeConverter = new StyleTypeConverter();
        var uriTypeConverter = new UriTypeConverter();
        var configurationTag = new TagName("!Configuration");
        var wireguardTag = new TagName("!Wireguard");
        var loggingTag = new TagName("!Logging");
        var webTag = new TagName("!Web");
        var trafficTag = new TagName("!Traffic");
        var trafficDriverTag = new TagName("!Json");
        _deserializer = new DeserializerBuilder()
            .WithNamingConvention(namingConvention)
            .WithTypeConverter(ipAddressCidrTypeConverter)
            .WithTypeConverter(networkInterfaceTypeConverter)
            .WithTypeConverter(uriTypeConverter)
            .WithTypeConverter(styleTypeConverter)
            .WithTagMapping(configurationTag, typeof(Configuration))
            .WithTagMapping(wireguardTag, typeof(WireguardConfiguration))
            .WithTagMapping(loggingTag, typeof(LoggingConfiguration))
            .WithTagMapping(webTag, typeof(WebConfiguration))
            .WithTagMapping(trafficTag, typeof(TrafficConfiguration))
            .WithTagMapping(trafficDriverTag, typeof(JsonTrafficStorageDriver))
            .Build();
        _serializer = new SerializerBuilder()
            .WithNamingConvention(namingConvention)
            .WithTypeConverter(ipAddressCidrTypeConverter)
            .WithTypeConverter(networkInterfaceTypeConverter)
            .WithTypeConverter(uriTypeConverter)
            .WithTypeConverter(styleTypeConverter)
            .WithTagMapping(configurationTag, typeof(Configuration))
            .WithTagMapping(wireguardTag, typeof(WireguardConfiguration))
            .WithTagMapping(loggingTag, typeof(LoggingConfiguration))
            .WithTagMapping(webTag, typeof(WebConfiguration))
            .WithTagMapping(trafficTag, typeof(TrafficConfiguration))
            .WithTagMapping(trafficDriverTag, typeof(JsonTrafficStorageDriver))
            .Build();
    }
    
    public string Serialize(IConfiguration configuration) {
        return _serializer.Serialize(configuration);
    }

    public IConfiguration Deserialize(string text) {
        return _deserializer.Deserialize<IConfiguration>(text);
    }
}