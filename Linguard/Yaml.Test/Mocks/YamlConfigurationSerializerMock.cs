using System.Collections.Generic;
using Core.Test.Mocks;
using Linguard.Core;
using Linguard.Core.Configuration;
using Linguard.Core.Configuration.Serialization;
using Linguard.Core.Drivers.TrafficStorage;
using Linguard.Core.Models.Wireguard;
using Linguard.Core.Plugins;
using Linguard.Json;
using Linguard.Web.Configuration;
using Linguard.Yaml.Serialization;
using Moq;
using YamlDotNet.Serialization.NamingConventions;

namespace Yaml.Test.Mocks;

public static class YamlConfigurationSerializerMock {
    
    public static IConfigurationSerializer Instance => 
        new YamlConfigurationSerializerBuilder()
            .WithNamingConvention(PascalCaseNamingConvention.Instance)
            .WithTypeConverter<IPAddressCidrTypeConverter>()
            .WithTypeConverter<NetworkInterfaceTypeConverterMock>()
            .WithTypeConverter<UriTypeConverter>()
            .WithTypeConverter(new TrafficStorageDriverConverter(new PluginEngineMock().Object))
            .WithTypeConverter<RuleTypeConverter>()
            .WithTypeMapping<IConfiguration, ConfigurationBase>()
            .WithTypeMapping<IWireguardConfiguration, WireguardConfiguration>()
            .WithTagMapping<WireguardConfiguration>("!Wireguard")
            .WithTypeMapping<IWebConfiguration, WebConfiguration>()
            .WithTagMapping<WebConfiguration>("!Web")
            .WithTypeMapping<ITrafficConfiguration, TrafficConfiguration>()
            .WithTagMapping<TrafficConfiguration>("!Traffic")
            .WithTypeMapping<ISet<Interface>, HashSet<Interface>>()
            .WithTypeMapping<ISet<Client>, HashSet<Client>>()
            .WithTypeMapping<ISet<IPAddressCidr>, HashSet<IPAddressCidr>>()
            .WithTypeMapping<ISet<Rule>, HashSet<Rule>>()
            .WithTypeMapping<ISet<IConfigurationModule>, HashSet<IConfigurationModule>>()
            .Build();
}