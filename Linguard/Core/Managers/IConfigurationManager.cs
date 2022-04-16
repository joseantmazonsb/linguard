using Linguard.Core.Configuration;
using Linguard.Core.Plugins;

namespace Linguard.Core.Managers; 

/// <summary>
/// Manages the configuration of the application, providing an upper level of abstraction
/// and relying on a working directory.
/// </summary>
public interface IConfigurationManager {
    /// <summary>
    /// Indicates where is the configuration.
    /// </summary>
    /// <remarks>Could be a path to a file, a connection string, etc.</remarks>
    string ConfigurationSource { get; set; }
    /// <summary>
    /// Configuration of the application.
    /// </summary>
    IConfiguration Configuration { get; set; }
    /// <summary>
    /// Manage plugins of the application.
    /// </summary>
    IPluginEngine PluginEngine { get; set; }
    /// <summary>
    /// Load default options.
    /// </summary>
    void LoadDefaults();
    /// <summary>
    /// Load the configuration.
    /// </summary>
    void Load();
    /// <summary>
    /// Save the current configuration.
    /// </summary>
    void Save();
    /// <summary>
    /// Export the current configuration to text.
    /// </summary>
    /// <returns></returns>
    string Export();
}