namespace Linguard.Core.Configuration.Serialization; 

public abstract class ConfigurationSerializerBase : IConfigurationSerializer {
    public abstract string Serialize<T>(T configuration) where T : IConfiguration;
    public T? Deserialize<T>(string text) where T : IConfiguration {
        LoadPlugins(text);
        return DeserializeAfterPluginsLoaded<T>(text);
    }
    /// <summary>
    /// Since there may be configuration dependent of what plugins have been loaded, this method gets called before
    /// actually mapping the whole configuration.
    /// </summary>
    /// <param name="text"></param>
    protected abstract void LoadPlugins(string text);
    /// <summary>
    /// Map the configuration to classes after all plugins have been loaded. 
    /// </summary>
    /// <param name="text"></param>
    /// <typeparam name="T"></typeparam>
    /// <returns></returns>
    protected abstract T DeserializeAfterPluginsLoaded<T>(string text) where T : IConfiguration;
}