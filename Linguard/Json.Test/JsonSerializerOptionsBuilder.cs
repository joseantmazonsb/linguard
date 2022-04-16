using System.Collections.Generic;
using System.Text.Json;
using Linguard.Core;
using Linguard.Core.Configuration;
using Linguard.Core.Models.Wireguard;
using Linguard.Core.OS;
using Linguard.Core.Plugins;
using Linguard.Json.Converters;

namespace Json.Test; 

public class JsonSerializerOptionsBuilder {
    private readonly ISystemWrapper _systemWrapper;
    private readonly IPluginEngine _pluginEngine;

    public JsonSerializerOptionsBuilder(ISystemWrapper systemWrapper, IPluginEngine pluginEngine) {
        _systemWrapper = systemWrapper;
        _pluginEngine = pluginEngine;
    }

    public JsonSerializerOptions Build() {
        return new JsonSerializerOptions {
            Converters = {
                new TypeMappingConverter<IConfiguration, ConfigurationBase>(),
                new TypeMappingConverter<IWireguardOptions, WireguardOptions>(),
                new TypeMappingConverter<ITrafficOptions, TrafficOptions>(),
                new TypeMappingConverter<IPluginOptions, PluginOptions>(),
                new TypeMappingConverter<ISet<Interface>, HashSet<Interface>>(),
                new TypeMappingConverter<ISet<Client>, HashSet<Client>>(),
                new TypeMappingConverter<ISet<IPAddressCidr>, HashSet<IPAddressCidr>>(),
                new TypeMappingConverter<ISet<Rule>, HashSet<Rule>>(),
                new TypeMappingConverter<ISet<IOptionsModule>, HashSet<IOptionsModule>>(),
                new IPAddressCidrConverter(),
                new NetworkInterfaceConverter(_systemWrapper),
                new UriConverter(),
                new RuleConverter(),
                new TrafficStorageDriverConverter(_pluginEngine),
                new ConfigurationModuleConverter(),
                new PluginConverter()
            }
        };
    }
}