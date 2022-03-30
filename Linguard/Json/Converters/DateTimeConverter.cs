using System.Text.Json;
using System.Text.Json.Serialization;

namespace Linguard.Json.Converters; 

public class DateTimeConverter : JsonConverter<DateTime> {

    private readonly string _format;
    
    public DateTimeConverter(string format) {
        _format = format;
    }
    
    public override DateTime Read(ref Utf8JsonReader reader, Type typeToConvert, JsonSerializerOptions options) {
        var dateStr = reader.GetString();
        var date = DateTime.ParseExact(dateStr, _format, default);
        return date;
    }

    public override void Write(Utf8JsonWriter writer, DateTime value, JsonSerializerOptions options) {
        writer.WriteStringValue(value.ToString(_format));
    }
}