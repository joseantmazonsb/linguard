using System.Text.Json;
using System.Text.Json.Serialization;
using Linguard.Core.Configuration;
using Linguard.Core.Models.Wireguard;

namespace Linguard.Json.Converters; 

public class WireguardPeerConverter : JsonConverter<IWireguardPeer> {
    private readonly IWireguardConfiguration _configuration;

    public WireguardPeerConverter(IWireguardConfiguration configuration) {
        _configuration = configuration;
    }

    public override IWireguardPeer? Read(ref Utf8JsonReader reader, Type typeToConvert, JsonSerializerOptions options) {
        var id = reader.GetGuid();
        var peer = _configuration.GetInterface(id) 
                   ?? _configuration.Interfaces.SingleOrDefault(p => p.Id.Equals(id));
        return peer;
    }

    public override void Write(Utf8JsonWriter writer, IWireguardPeer value, JsonSerializerOptions options) {
        writer.WriteStringValue(value.Id.ToString());
    }
}