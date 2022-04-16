using System.Text.Json;
using System.Text.Json.Serialization;

namespace Linguard.Json.Converters; 

public class DirectoryInfoConverter : JsonConverter<DirectoryInfo> {
    public override DirectoryInfo? Read(ref Utf8JsonReader reader, Type typeToConvert, JsonSerializerOptions options) {
        var value = reader.GetString();
        return value != default ? new DirectoryInfo(value) : default;
    }

    public override void Write(Utf8JsonWriter writer, DirectoryInfo value, JsonSerializerOptions options) {
        writer.WriteStringValue(value.FullName);
    }
}