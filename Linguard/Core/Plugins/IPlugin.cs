using Linguard.Core.Annotations;
using Linguard.Core.Managers;

namespace Linguard.Core.Plugins; 

public interface IPlugin : ICloneable {
    /// <summary>
    /// Name of the plugin.
    /// </summary>
    [Mandatory]
    string Name { get; }
    /// <summary>
    /// Brief description of the plugin's behaviour.
    /// </summary>
    [Optional]
    string Description { get; }
    /// <summary>
    /// Initialize the plugin.
    /// </summary>
    /// <remarks>This method should be called before the plugin performs any operation.</remarks>
    /// <param name="configurationManager"></param>
    void Initialize(IConfigurationManager configurationManager);
}