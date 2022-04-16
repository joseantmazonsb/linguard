using System.Text.Json;
using Linguard.Core.Configuration;
using Linguard.Core.Configuration.Serialization;
using Linguard.Core.Plugins;

namespace Linguard.Json;

public abstract class JsonConfigurationSerializer : ConfigurationSerializerBase {
    
    private readonly JsonSerializerOptions _serializerOptions;
    private readonly IPluginEngine _pluginEngine;

    protected JsonConfigurationSerializer(JsonSerializerOptions options, IPluginEngine pluginEngine) {
        _serializerOptions = options;
        _pluginEngine = pluginEngine;
    }

    public override string Serialize<T>(T configuration) {
        return JsonSerializer.Serialize(configuration, _serializerOptions);
    }

    protected override T DeserializeAfterPluginsLoaded<T>(string text) {
        return JsonSerializer.Deserialize<T>(text, _serializerOptions);
    }

    protected override void LoadPlugins(string text) {
        var dictionary = JsonSerializer.Deserialize<IDictionary<string, object>>(text);
        var plugins = dictionary["Plugins"].ToString();
        var pluginConfiguration = JsonSerializer.Deserialize<IPluginOptions>(plugins, _serializerOptions);
        _pluginEngine.LoadPlugins(pluginConfiguration.PluginsDirectory);
    }
}