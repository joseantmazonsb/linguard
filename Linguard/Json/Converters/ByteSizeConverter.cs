using System.Text.Json;
using System.Text.Json.Serialization;
using ByteSizeLib;

namespace Linguard.Json.Converters; 

public class ByteSizeConverter : JsonConverter<ByteSize> {
    
    public override ByteSize Read(ref Utf8JsonReader reader, Type typeToConvert, JsonSerializerOptions options) {
        var bytes = reader.GetDouble();
        return ByteSize.FromBytes(bytes);
    }

    public override void Write(Utf8JsonWriter writer, ByteSize value, JsonSerializerOptions options) {
        writer.WriteNumberValue(value.Bytes);
    }
}