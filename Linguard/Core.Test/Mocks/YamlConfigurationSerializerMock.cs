﻿using System.Collections.Generic;
using Linguard.Core;
using Linguard.Core.Configuration;
using Linguard.Core.Configuration.Serialization;
using Linguard.Core.Drivers.TrafficStorage;
using Linguard.Core.Models.Wireguard;
using YamlDotNet.Serialization.NamingConventions;

namespace Core.Test.Mocks;

public static class YamlConfigurationSerializerMock {
    
    public static YamlConfigurationSerializer Instance => new YamlConfigurationSerializerBuilder()
            .WithNamingConvention(PascalCaseNamingConvention.Instance)
            .WithTypeConverter<IPAddressCidrTypeConverter>()
            .WithTypeConverter<NetworkInterfaceTypeConverterMock>()
            .WithTypeConverter<UriTypeConverter>()
            .WithTypeConverter<StyleTypeConverter>()
            .WithTypeMapping<IConfiguration, Configuration>()
            .WithTypeMapping<IWireguardConfiguration, WireguardConfiguration>()
            .WithTypeMapping<ILoggingConfiguration, LoggingConfiguration>()
            .WithTypeMapping<IWebConfiguration, WebConfiguration>()
            .WithTypeMapping<ITrafficConfiguration, TrafficConfiguration>()
            .WithTypeMapping<ITrafficStorageDriver, JsonTrafficStorageDriver>()
            .WithTypeMapping<ISet<Interface>, HashSet<Interface>>()
            .WithTypeMapping<ISet<Client>, HashSet<Client>>()
            .WithTypeMapping<ISet<IPAddressCidr>, HashSet<IPAddressCidr>>()
            .WithTypeMapping<ISet<Rule>, HashSet<Rule>>()
            .Build();
}