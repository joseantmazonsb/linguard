using System.Text.Json;
using Linguard.Core;
using Linguard.Core.Configuration;
using Linguard.Core.Models.Wireguard;
using Linguard.Core.OS;
using Linguard.Core.Plugins;
using Linguard.Json;
using Linguard.Json.Converters;

namespace Linguard.Web.Configuration.Serialization;

public class JsonConfigurationSerializerWeb : JsonConfigurationSerializer {

    public JsonConfigurationSerializerWeb(ISystemWrapper systemWrapper, IPluginEngine pluginEngine) 
        : base(new JsonSerializerOptions {
        Converters = {
            new TypeMappingConverter<IConfiguration, Configuration>(),
            new TypeMappingConverter<Core.Configuration.IConfiguration, Configuration>(),
            new TypeMappingConverter<IWireguardOptions, WireguardOptions>(),
            new TypeMappingConverter<ITrafficOptions, TrafficOptions>(),
            new TypeMappingConverter<IWebOptions, WebOptions>(),
            new TypeMappingConverter<IPluginOptions, PluginOptions>(),
            new TypeMappingConverter<IAuthenticationOptions, AuthenticationOptions>(),
            new TypeMappingConverter<ISet<Interface>, HashSet<Interface>>(),
            new TypeMappingConverter<ISet<Client>, HashSet<Client>>(),
            new TypeMappingConverter<ISet<IPAddressCidr>, HashSet<IPAddressCidr>>(),
            new TypeMappingConverter<ISet<Rule>, HashSet<Rule>>(),
            new TypeMappingConverter<ISet<IOptionsModule>, HashSet<IOptionsModule>>(),
            new IPAddressCidrConverter(),
            new NetworkInterfaceConverter(systemWrapper),
            new UriConverter(),
            new RuleConverter(),
            new TrafficStorageDriverConverter(pluginEngine),
            new DirectoryInfoConverter()
        },
        WriteIndented = true,
        PropertyNameCaseInsensitive = true
    }, pluginEngine) 
    { }
}