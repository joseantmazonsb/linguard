using System.Collections.Generic;
using System.Text.Json;
using System.Text.Json.Serialization;
using Linguard.Core;
using Linguard.Core.Configuration;
using Linguard.Core.Models.Wireguard;
using Linguard.Core.OS;
using Linguard.Core.Plugins;
using Linguard.Json;
using Linguard.Json.Converters;

namespace Json.Test.Stubs; 

public class JsonConfigurationSerializerStub : JsonConfigurationSerializer {

    public JsonConfigurationSerializerStub(ISystemWrapper systemWrapper, IPluginEngine pluginEngine) : base(new JsonSerializerOptions {
        Converters = {
            new TypeMappingConverter<IConfiguration, ConfigurationBase>(),
            new TypeMappingConverter<IWireguardOptions, WireguardOptions>(),
            new TypeMappingConverter<ITrafficOptions, TrafficOptions>(),
            new TypeMappingConverter<IPluginOptions, PluginOptions>(),
            new TypeMappingConverter<IAuthenticationOptions, AuthenticationOptions>(),
            new TypeMappingConverter<ISet<Interface>, HashSet<Interface>>(),
            new TypeMappingConverter<ISet<Client>, HashSet<Client>>(),
            new TypeMappingConverter<ISet<IPAddressCidr>, HashSet<IPAddressCidr>>(),
            new TypeMappingConverter<ISet<Rule>, HashSet<Rule>>(),
            new TypeMappingConverter<IDictionary<string, IOptionsModule>, Dictionary<string, IOptionsModule>>(),
            new IPAddressCidrConverter(),
            new NetworkInterfaceConverter(systemWrapper),
            new UriConverter(),
            new RuleConverter(),
            new TrafficStorageDriverConverter(pluginEngine),
            new ConfigurationModuleConverter(),
            new PluginConverter(),
            new DirectoryInfoConverter()
        },
        WriteIndented = true
    }, pluginEngine) 
    { }
}