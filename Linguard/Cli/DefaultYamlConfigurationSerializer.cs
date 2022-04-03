using Linguard.Core;
using Linguard.Core.Configuration;
using Linguard.Core.Configuration.Serialization;
using Linguard.Core.Drivers.TrafficStorage;
using Linguard.Core.Models.Wireguard;
using Linguard.Json;
using Linguard.Yaml.Serialization;
using YamlDotNet.Serialization.NamingConventions;
using UriTypeConverter = Linguard.Yaml.Serialization.UriTypeConverter;

namespace Linguard.Cli; 

public static class DefaultYamlConfigurationSerializer {

    public static IConfigurationSerializer Instance => new YamlConfigurationSerializerBuilder()
        .WithNamingConvention(PascalCaseNamingConvention.Instance)
        .WithTypeConverter<IPAddressCidrTypeConverter>()
        .WithTypeConverter<NetworkInterfaceTypeConverter>()
        .WithTypeConverter<UriTypeConverter>()
        .WithTypeMapping<IConfiguration, ConfigurationBase>()
        .WithTypeMapping<IWireguardConfiguration, WireguardConfiguration>()
        .WithTypeMapping<ITrafficConfiguration, TrafficConfiguration>()
        .WithTypeMapping<ITrafficStorageDriver, TrafficStorageDriver>()
        .WithTypeMapping<ISet<Interface>, HashSet<Interface>>()
        .WithTypeMapping<ISet<Client>, HashSet<Client>>()
        .WithTypeMapping<ISet<IPAddressCidr>, HashSet<IPAddressCidr>>()
        .WithTypeMapping<ISet<Rule>, HashSet<Rule>>()
        .Build();
}