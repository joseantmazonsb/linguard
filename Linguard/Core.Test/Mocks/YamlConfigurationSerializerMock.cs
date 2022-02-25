using Linguard.Core.Configuration;
using Linguard.Core.Configuration.Serialization;
using Linguard.Core.Drivers.TrafficStorage;
using YamlDotNet.Serialization.NamingConventions;

namespace Core.Test.Mocks;

public static class YamlConfigurationSerializerMock {
    
    public static YamlConfigurationSerializer Instance => new YamlConfigurationSerializerBuilder()
            .WithNamingConvention(PascalCaseNamingConvention.Instance)
            .WithTypeConverter<IPAddressCidrTypeConverter>()
            .WithTypeConverter<NetworkInterfaceTypeConverterMock>()
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