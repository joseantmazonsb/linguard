﻿using Linguard.Core.Managers;

namespace Linguard.Core.Plugins; 

public interface IPluginEngine {
    IEnumerable<IPlugin> Plugins { get; }

    /// <summary>
    /// Load plugins from the given directory.
    /// </summary>
    /// <param name="pluginsDirectory"></param>
    /// <param name="configurationManager"></param>
    /// <returns>The amount of plugins successfully loaded.</returns>
    int LoadPlugins(DirectoryInfo pluginsDirectory, IConfigurationManager configurationManager);
}