using System.Reflection;
using Linguard.Core.Managers;
using Microsoft.Extensions.Logging;

namespace Linguard.Core.Plugins; 

public class PluginEngine : IPluginEngine {
    private readonly ILogger<IPluginEngine> _logger;

    public PluginEngine(ILogger<PluginEngine> logger) {
        _logger = logger;
    }

    private readonly IDictionary<Type, IPlugin> _plugins = new Dictionary<Type, IPlugin>();
    public IEnumerable<IPlugin> Plugins => _plugins.Values;

    public int LoadPlugins(DirectoryInfo directory) {
        var plugins = new List<IPlugin>();
        foreach (var file in directory.EnumerateFiles()) {
            try {
                _logger.LogDebug($"Loading plugins from file {file.FullName}...");
                var p = LoadPlugins(file).ToList();
                _logger.LogDebug($"Loaded {p.Count} plugins from file {file.FullName}.");
                plugins.AddRange(p);
            }
            catch (Exception e) {
                _logger.LogError(e, $"Unable to load plugins from file {file.FullName}.");
            } 
        }
        foreach (var plugin in plugins) {
            _plugins[plugin.GetType()] = plugin;
        }
        return plugins.Count;
    }

    public void InitializePlugins(IConfigurationManager configurationManager) {
        foreach (var plugin in Plugins) {
            _logger.LogTrace($"Initializing plugin {plugin.Name}...");
            plugin.Initialize(configurationManager);
            _logger.LogTrace($"Plugin {plugin.Name} was initialized successfully.");
        }
    }

    private IEnumerable<IPlugin> LoadPlugins(FileInfo file) {
        var context = new PluginLoadContext(file);
        var assemblyName = new AssemblyName(Path.GetFileNameWithoutExtension(file.FullName));
        var assembly = context.LoadFromAssemblyName(assemblyName);
        var plugins = new List<IPlugin>();
        foreach (var type in assembly.ExportedTypes) {
            if (type.GetInterface(nameof(IPlugin)) == default) continue;
            if (_plugins.ContainsKey(type)) continue;
            try {
                _logger.LogTrace($"Loading plugin {type.FullName} from assembly {assembly.FullName}...");
                var plugin = (IPlugin)Activator.CreateInstance(type)!;
                _logger.LogTrace($"Plugin {plugin.Name} was loaded successfully.");
                plugins.Add(plugin);
            }
            catch (Exception e) {
                _logger.LogError(e, $"Failed to load plugin {type.FullName} from assembly {assembly.FullName}.");
            }
        }
        return plugins;
    }
}