using Linguard.Core.Configuration;
using Linguard.Log;

namespace Linguard.Core.Managers; 

/// <summary>
/// Manages the configuration of the application, providing an upper level of abstraction
/// and relying on a working directory.
/// </summary>
public interface IConfigurationManager {
    /// <summary>
    /// Configuration of the application.
    /// </summary>
    IConfiguration Configuration { get; set; }
    /// <summary>
    /// Working directory of the application.
    /// </summary>
    IWorkingDirectory WorkingDirectory { get; set; }
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