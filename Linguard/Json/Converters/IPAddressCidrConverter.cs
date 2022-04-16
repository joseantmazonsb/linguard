using System.Text.Json;
using System.Text.Json.Serialization;
using Linguard.Core;

namespace Linguard.Json.Converters;

public class IPAddressCidrConverter : JsonConverter<IPAddressCidr> {
    
    public override IPAddressCidr? Read(ref Utf8JsonReader reader, Type typeToConvert, JsonSerializerOptions options) {
        var value = reader.GetString();
        return value != default ? IPAddressCidr.Parse(value) : default;
    }

    public override void Write(Utf8JsonWriter writer, IPAddressCidr? value, JsonSerializerOptions options) {
        writer.WriteStringValue(value?.ToString() ?? string.Empty);
    }
}