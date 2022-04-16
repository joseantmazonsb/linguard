using System.Text.Json;
using System.Text.Json.Serialization;
using Linguard.Core.Models.Wireguard;

namespace Linguard.Json.Converters;

public class RuleConverter : JsonConverter<Rule> {

    public override Rule? Read(ref Utf8JsonReader reader, Type typeToConvert, JsonSerializerOptions options) {
        var value = reader.GetString();
        return value ?? string.Empty;
    }

    public override void Write(Utf8JsonWriter writer, Rule value, JsonSerializerOptions options) {
        writer.WriteStringValue(value.Command);
    }
}