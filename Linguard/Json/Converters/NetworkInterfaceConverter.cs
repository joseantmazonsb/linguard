using System.Net.NetworkInformation;
using System.Text.Json;
using System.Text.Json.Serialization;
using Linguard.Core.OS;

namespace Linguard.Json.Converters;

public class NetworkInterfaceConverter : JsonConverter<NetworkInterface> {
    
    private readonly ISystemWrapper _systemWrapper;
    
    public NetworkInterfaceConverter(ISystemWrapper systemWrapper) {
        _systemWrapper = systemWrapper;
    }
    
    public override NetworkInterface? Read(ref Utf8JsonReader reader, Type typeToConvert, JsonSerializerOptions options) {
        var value = reader.GetString();
        return value != default 
            ? _systemWrapper.NetworkInterfaces
                .SingleOrDefault(i => i.Name.Equals(value, StringComparison.InvariantCultureIgnoreCase)) 
            : default;
    }

    public override void Write(Utf8JsonWriter writer, NetworkInterface value, JsonSerializerOptions options) {
        writer.WriteStringValue(value.Name);
    }
}