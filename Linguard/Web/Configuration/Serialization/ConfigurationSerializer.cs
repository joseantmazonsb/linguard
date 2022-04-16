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
                .WithTypeMapping<IConfiguration, Configuration>()
                .WithTypeMapping<IWireguardOptions, WireguardOptions>()
                .WithTypeMapping<ITrafficOptions, TrafficOptions>()
                .WithTypeMapping<IWebOptions, WebOptions>()
                .WithTagMapping<WireguardOptions>("!Wireguard")
                .WithTagMapping<TrafficOptions>("!Traffic")
                .WithTagMapping<WebOptions>("!Web")
                .WithTypeMapping<ISet<Interface>, HashSet<Interface>>()
                .WithTypeMapping<ISet<Client>, HashSet<Client>>()
                .WithTypeMapping<ISet<IPAddressCidr>, HashSet<IPAddressCidr>>()
                .WithTypeMapping<ISet<Rule>, HashSet<Rule>>()
                .WithTypeMapping<ISet<IOptionsModule>, HashSet<IOptionsModule>>()
                .Build();
    
    public string Serialize<T>(T configuration) where T : Core.Configuration.IConfiguration {
        return Serializer.Serialize(configuration);
    }

    public T? Deserialize<T>(string text) where T : Core.Configuration.IConfiguration {
        return Serializer.Deserialize<T>(text);
    }
}