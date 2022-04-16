using System.Text.Json;
using System.Text.Json.Serialization;
using Linguard.Core.Drivers.TrafficStorage;
using Linguard.Core.Plugins;

namespace Linguard.Json.Converters;

public class TrafficStorageDriverConverter : JsonConverter<ITrafficStorageDriver> {
    private readonly IPluginEngine _pluginEngine;

    public TrafficStorageDriverConverter(IPluginEngine pluginEngine) {
        _pluginEngine = pluginEngine;
    }
    
    public override ITrafficStorageDriver? Read(ref Utf8JsonReader reader, Type typeToConvert, JsonSerializerOptions options) {
        var properties = new Dictionary<string, object>(); 
        while (reader.TokenType is not JsonTokenType.EndObject) {
            reader.Read();
            var property = reader.GetString()!;
            reader.Read();
            switch (property) {
                case nameof(ITrafficStorageDriver.Name):
                    var name = reader.GetString()!;
                    properties[nameof(ITrafficStorageDriver.Name)] = name;
                    break;
                case nameof(ITrafficStorageDriver.Description):
                    break;
                case nameof(ITrafficStorageDriver.CollectionInterval):
                    var value = reader.GetString()!;
                    var interval = TimeSpan.Parse(value);
                    properties[nameof(ITrafficStorageDriver.CollectionInterval)] = interval;
                    break;
                case nameof(ITrafficStorageDriver.AdditionalOptions):
                    ParseDictionary(ref reader, properties, nameof(ITrafficStorageDriver.AdditionalOptions));
                    break;
            }
        }
        reader.Read();
        var driverName = (string) properties[nameof(ITrafficStorageDriver.Name)];
        var driver = _pluginEngine.Plugins
            .OfType<ITrafficStorageDriver>()
            .SingleOrDefault(p => p.Name.Equals(driverName));
        if (driver == default) {
            throw new JsonException($"No instance of {nameof(ITrafficStorageDriver)} " +
                                    $"named '{driverName}' was found. Maybe you forgot to add a plugin?");
        }
        driver.CollectionInterval = (TimeSpan) properties[nameof(ITrafficStorageDriver.CollectionInterval)];
        driver.AdditionalOptions = (IDictionary<string, string>) properties[nameof(ITrafficStorageDriver.AdditionalOptions)];
        return driver;
    }
    
    private void ParseDictionary(ref Utf8JsonReader reader, IDictionary<string, object> properties, string name) {
        var dict = new Dictionary<string, string>();
        reader.Read();
        while (reader.TokenType is not JsonTokenType.EndObject) {
            var key = reader.GetString()!;
            reader.Read();
            var value = reader.GetString();
            dict[key] = value ?? string.Empty;
            reader.Read();
        }
        properties[name] = dict;
    }

    public override void Write(Utf8JsonWriter writer, ITrafficStorageDriver value, JsonSerializerOptions options) {
        JsonSerializer.Serialize(writer, value, value.GetType(), options);
    }
}