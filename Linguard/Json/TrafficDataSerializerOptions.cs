using System.Text.Json;
using Linguard.Core.Configuration;
using Linguard.Core.Models;
using Linguard.Json.Converters;

namespace Linguard.Json; 

public static class TrafficDataSerializerOptions {
    public static JsonSerializerOptions Build(IWireguardConfiguration wireguardConfiguration, 
        string timestampFormat) => new() { 
            Converters = { 
                new ByteSizeConverter(), 
                new WireguardPeerConverter(wireguardConfiguration), 
                new DateTimeConverter(timestampFormat), 
                new TypeMappingConverter<ITrafficData, TrafficData>()
        }
    };
}