using System.Collections.Generic;
using Core.Test.Mocks;
using Linguard.Core;
using Linguard.Core.Configuration;
using Linguard.Core.Configuration.Serialization;
using Linguard.Core.Drivers.TrafficStorage;
using Linguard.Core.Models.Wireguard;
using Linguard.Yaml.Serialization;
using YamlDotNet.Serialization.NamingConventions;

namespace Yaml.Test.Mocks;

public static class YamlConfigurationSerializerMock {
    
    public static IConfigurationSerializer Instance => 
        new YamlConfigurationSerializerBuilder()
            .WithNamingConvention(PascalCaseNamingConvention.Instance)
            .WithTypeConverter<IPAddressCidrTypeConverter>()
            .WithTypeConverter<NetworkInterfaceTypeConverterMock>()
            .WithTypeConverter<UriTypeConverter>()
            .WithTypeMapping<IConfiguration, ConfigurationBase>()
            .WithTypeMapping<IWireguardConfiguration, WireguardConfiguration>()
            .WithTypeMapping<ILoggingConfiguration, LoggingConfiguration>()
            .WithTypeMapping<ITrafficConfiguration, TrafficConfiguration>()
            .WithTagMapping<WireguardConfiguration>("!Wireguard")
            .WithTagMapping<LoggingConfiguration>("!Logging")
            .WithTagMapping<TrafficConfiguration>("!Traffic")
            .WithTypeMapping<ITrafficStorageDriver, JsonTrafficStorageDriver>()
            .WithTypeMapping<ISet<Interface>, HashSet<Interface>>()
            .WithTypeMapping<ISet<Client>, HashSet<Client>>()
            .WithTypeMapping<ISet<IPAddressCidr>, HashSet<IPAddressCidr>>()
            .WithTypeMapping<ISet<Rule>, HashSet<Rule>>()
            .WithTypeMapping<ISet<IConfigurationModule>, HashSet<IConfigurationModule>>()
            .Build();
}