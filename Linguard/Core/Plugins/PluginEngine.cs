using System.Reflection;
using Linguard.Core.Managers;
using Microsoft.Extensions.Logging;

namespace Linguard.Core.Plugins; 

public class PluginEngine : IPluginEngine {
    private readonly ILogger<IPluginEngine> _logger;

    public PluginEngine(ILogger<PluginEngine> logger) {
        _logger = logger;
    }

    private readonly List<IPlugin> _plugins = new();
    public IEnumerable<IPlugin> Plugins => _plugins;

    public int LoadPlugins(DirectoryInfo pluginsDirectory, IConfigurationManager configurationManager) {
        var plugins = new List<IPlugin>();
        foreach (var file in pluginsDirectory.EnumerateFiles()) {
            try {
                _logger.LogDebug($"Loading plugins from file {file.FullName}...");
                var p = LoadPlugins(file, configurationManager).ToList();
                _logger.LogDebug($"Loaded {p.Count} plugins from file {file.FullName}.");
                plugins.AddRange(p);
            }
            catch (Exception e) {
                _logger.LogError(e, $"Unable to load plugins from file {file.FullName}.");
            } 
        }
        _plugins.AddRange(plugins);
        return plugins.Count;
    }

    private IEnumerable<IPlugin> LoadPlugins(FileInfo file, IConfigurationManager configurationManager) {
        var context = new PluginLoadContext(file);
        var assemblyName = new AssemblyName(Path.GetFileNameWithoutExtension(file.FullName));
        var assembly = context.LoadFromAssemblyName(assemblyName);
        var plugins = new List<IPlugin>();
        foreach (var type in assembly.ExportedTypes) {
            if (type.GetInterface(nameof(IPlugin)) == default) continue;
            try {
                _logger.LogTrace($"Loading plugin {type.FullName} from assembly {assembly.FullName}...");
                var plugin = (IPlugin)Activator.CreateInstance(type)!;
                _logger.LogTrace($"Plugin {plugin.Name} was loaded successfully.");
                _logger.LogTrace($"Initializing plugin {plugin.Name}...");
                plugin.Initialize(configurationManager);
                _logger.LogTrace($"Plugin {plugin.Name} was initialized successfully.");
                plugins.Add(plugin);
            }
            catch (Exception e) {
                _logger.LogError(e, $"Failed to load plugin {type.FullName} from assembly {assembly.FullName}.");
            }
        }
        return plugins;
    }
}