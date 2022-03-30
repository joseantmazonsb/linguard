using Linguard.Core;
using Linguard.Core.Configuration;
using Linguard.Core.Configuration.Serialization;
using Linguard.Core.Models.Wireguard;
using Linguard.Core.Plugins;
using Linguard.Yaml.Serialization;
using YamlDotNet.Serialization.NamingConventions;
using IConfiguration = Linguard.Core.Configuration.IConfiguration;
using UriTypeConverter = Linguard.Yaml.Serialization.UriTypeConverter;


namespace Linguard.Web.Configuration.Serialization; 

public class ConfigurationSerializer : IConfigurationSerializer {

    private readonly IPluginEngine _pluginEngine;
    
    private IConfigurationSerializer? _serializer;

    public ConfigurationSerializer(IPluginEngine pluginEngine) {
        _pluginEngine = pluginEngine;
    }

    private IConfigurationSerializer Serializer =>
        _serializer ??= 
            new YamlConfigurationSerializerBuilder()
                .WithNamingConvention(PascalCaseNamingConvention.Instance)
                .WithTypeConverter<IPAddressCidrTypeConverter>()
                .WithTypeConverter<NetworkInterfaceTypeConverter>()
                .WithTypeConverter<UriTypeConverter>()
                .WithTypeConverter(new TrafficStorageDriverConverter(_pluginEngine))
                .WithTypeConverter<RuleTypeConverter>()
                .WithTypeMapping<IConfiguration, ConfigurationBase>()
                .WithTypeMapping<IWireguardConfiguration, WireguardConfiguration>()
                .WithTypeMapping<ILoggingConfiguration, LoggingConfiguration>()
                .WithTypeMapping<ITrafficConfiguration, TrafficConfiguration>()
                .WithTypeMapping<IWebConfiguration, WebConfiguration>()
                .WithTagMapping<WireguardConfiguration>("!Wireguard")
                .WithTagMapping<LoggingConfiguration>("!Logging")
                .WithTagMapping<TrafficConfiguration>("!Traffic")
                .WithTagMapping<WebConfiguration>("!Web")
                .WithTypeMapping<ISet<Interface>, HashSet<Interface>>()
                .WithTypeMapping<ISet<Client>, HashSet<Client>>()
                .WithTypeMapping<ISet<IPAddressCidr>, HashSet<IPAddressCidr>>()
                .WithTypeMapping<ISet<Rule>, HashSet<Rule>>()
                .WithTypeMapping<ISet<IConfigurationModule>, HashSet<IConfigurationModule>>()
                .Build();
    
    public string Serialize<T>(T configuration) where T : IConfiguration {
        return Serializer.Serialize(configuration);
    }

    public T Deserialize<T>(string text) where T : IConfiguration {
        return Serializer.Deserialize<T>(text);
    }
}