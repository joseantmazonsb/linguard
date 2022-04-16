using System.Text.Json;
using System.Text.Json.Serialization;
using Linguard.Core.Configuration;

namespace Linguard.Json.Converters; 

public class ConfigurationModuleConverter : JsonConverter<IOptionsModule> {
    public override IOptionsModule? Read(ref Utf8JsonReader reader, Type typeToConvert, JsonSerializerOptions options) {
        var newOptions = new JsonSerializerOptions(options);
        newOptions.Converters.Remove(this);
        var module = JsonSerializer.Deserialize(ref reader, typeToConvert, newOptions) as IOptionsModule;
        return module;
    }

    public override void Write(Utf8JsonWriter writer, IOptionsModule value, JsonSerializerOptions options) {
        JsonSerializer.Serialize(writer, value, value.GetType(), options);
    }
}