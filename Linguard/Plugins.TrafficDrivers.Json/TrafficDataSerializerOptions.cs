using System.Text.Json;
using Linguard.Core.Configuration;
using Linguard.Core.Models;
using Linguard.Json.Converters;
using Linguard.Plugins.TrafficDrivers.Json.Converters;

namespace Linguard.Plugins.TrafficDrivers.Json; 

public static class TrafficDataSerializerOptions {
    public static JsonSerializerOptions Build(IWireguardOptions wireguardOptions, 
        string timestampFormat) => new() { 
            Converters = { 
                new ByteSizeConverter(), 
                new WireguardPeerConverter(wireguardOptions), 
                new DateTimeConverter(timestampFormat), 
                new TypeMappingConverter<ITrafficData, TrafficData>()
        }
    };
}