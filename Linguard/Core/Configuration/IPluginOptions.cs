namespace Linguard.Core.Configuration; 

public interface IPluginOptions : IOptionsModule {
    /// <summary>
    /// Directory containing all plugins.
    /// </summary>
    DirectoryInfo PluginsDirectory { get; set; }
}