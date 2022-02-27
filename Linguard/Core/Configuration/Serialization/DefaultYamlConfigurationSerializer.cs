using Linguard.Core.Drivers.TrafficStorage;
using YamlDotNet.Serialization.NamingConventions;

namespace Linguard.Core.Configuration.Serialization; 

public static class DefaultYamlConfigurationSerializer {

    public static YamlConfigurationSerializer Instance => new YamlConfigurationSerializerBuilder()
        .WithNamingConvention(PascalCaseNamingConvention.Instance)
        .WithTypeConverter<IPAddressCidrTypeConverter>()
        .WithTypeConverter<NetworkInterfaceTypeConverter>()
        .WithTypeConverter<UriTypeConverter>()
        .WithTypeConverter<StyleTypeConverter>()
        .WithTagMapping<Configuration>("!Configuration")
        .WithTagMapping<WireguardConfiguration>("!Wireguard")
        .WithTagMapping<LoggingConfiguration>("!Logging")
        .WithTagMapping<WebConfiguration>("!Web")
        .WithTagMapping<TrafficConfiguration>("!Traffic")
        .WithTagMapping<JsonTrafficStorageDriver>("!Json")
        .Build();
}