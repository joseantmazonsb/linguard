using System.Text.Json;
using System.Text.Json.Serialization;
using Linguard.Core.Plugins;

namespace Linguard.Json.Converters; 

public class PluginConverter : JsonConverter<IPlugin> {
    public override IPlugin? Read(ref Utf8JsonReader reader, Type typeToConvert, JsonSerializerOptions options) {
        var value = reader.GetString()!;
        return JsonSerializer.Deserialize(value, typeToConvert, options) as IPlugin;
    }

    public override void Write(Utf8JsonWriter writer, IPlugin value, JsonSerializerOptions options) {
        JsonSerializer.Serialize(writer, value, value.GetType(), options);
    }
}