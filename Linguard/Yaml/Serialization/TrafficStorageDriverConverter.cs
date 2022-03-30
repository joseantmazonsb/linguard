using Linguard.Core.Drivers.TrafficStorage;
using Linguard.Core.Plugins;
using YamlDotNet.Core;
using YamlDotNet.Core.Events;
using YamlDotNet.Serialization;

namespace Linguard.Yaml.Serialization;

public class TrafficStorageDriverConverter : IYamlTypeConverter {

    private readonly IPluginEngine _pluginEngine;

    public TrafficStorageDriverConverter(IPluginEngine pluginEngine) {
        _pluginEngine = pluginEngine;
    }

    public bool Accepts(Type type) {
        return type == typeof(ITrafficStorageDriver) ||  type.GetInterface(nameof(ITrafficStorageDriver)) != default;
    }

    public object? ReadYaml(IParser parser, Type type) {
        parser.MoveNext();
        var properties = new Dictionary<string, object>(); 
        while (parser.Current is not MappingEnd) {
            var property = parser.Consume<Scalar>().Value;
            switch (property) {
                case nameof(ITrafficStorageDriver.Name):
                    var name = parser.Consume<Scalar>().Value;
                    properties[nameof(ITrafficStorageDriver.Name)] = name;
                    break;
                case nameof(ITrafficStorageDriver.Description):
                    // Ignore
                    parser.MoveNext();
                    break;
                case nameof(ITrafficStorageDriver.CollectionInterval):
                    if (!double.TryParse(parser.Consume<Scalar>().Value, out var interval)) {
                        interval = TimeSpan.FromHours(1).TotalSeconds;
                    }
                    properties[nameof(ITrafficStorageDriver.CollectionInterval)] = TimeSpan.FromSeconds(interval);
                    break;
                case nameof(ITrafficStorageDriver.AdditionalOptions):
                    ParseDictionary(parser, properties, nameof(ITrafficStorageDriver.AdditionalOptions));
                    break;
            }
        }
        parser.MoveNext();
        var driverName = (string) properties[nameof(ITrafficStorageDriver.Name)];
        var driver = _pluginEngine.Plugins
            .OfType<ITrafficStorageDriver>()
            .SingleOrDefault(p => p.Name.Equals(driverName));
        if (driver == default) {
            throw new YamlException($"No instance of {nameof(ITrafficStorageDriver)} " +
                                    $"named '{driverName}' was found. Maybe you forgot to add a plugin?");
        }
        driver.CollectionInterval = (TimeSpan) properties[nameof(ITrafficStorageDriver.CollectionInterval)];
        driver.AdditionalOptions = (IDictionary<string, string>) properties[nameof(ITrafficStorageDriver.AdditionalOptions)];
        return driver;
    }

    private void ParseDictionary(IParser parser, IDictionary<string, object> properties, string name) {
        var dict = new Dictionary<string, string>();
        parser.MoveNext(); // Skip MappingStart
        while (parser.Current is not MappingEnd) {
            var key = parser.Consume<Scalar>().Value;
            parser.TryConsume<Scalar>(out var value);
            dict[key] = value?.Value ?? string.Empty;
        }
        parser.MoveNext();
        properties[name] = dict;
    }

    public void WriteYaml(IEmitter emitter, object? value, Type type) {
        // Use default serialization
        var serializer = new SerializerBuilder()
            .BuildValueSerializer();
        serializer.SerializeValue(emitter, value, type);
    }
}