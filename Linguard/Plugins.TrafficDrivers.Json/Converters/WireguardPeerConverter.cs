using System.Text.Json;
using System.Text.Json.Serialization;
using Linguard.Core.Configuration;
using Linguard.Core.Models.Wireguard;

namespace Linguard.Plugins.TrafficDrivers.Json.Converters; 

public class WireguardPeerConverter : JsonConverter<IWireguardPeer> {
    private readonly IWireguardOptions _options;

    public WireguardPeerConverter(IWireguardOptions options) {
        _options = options;
    }

    public override IWireguardPeer? Read(ref Utf8JsonReader reader, Type typeToConvert, JsonSerializerOptions options) {
        var publicKey = reader.GetString();
        var peer = _options.GetInterface(publicKey) 
                   ?? _options.Interfaces.SingleOrDefault(p => p.PublicKey.Equals(publicKey));
        return peer;
    }

    public override void Write(Utf8JsonWriter writer, IWireguardPeer value, JsonSerializerOptions options) {
        writer.WriteStringValue(value.PublicKey);
    }
}