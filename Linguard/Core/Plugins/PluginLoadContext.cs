using System.Reflection;
using System.Runtime.Loader;

namespace Linguard.Core.Plugins; 

public class PluginLoadContext : AssemblyLoadContext {
    private readonly AssemblyDependencyResolver _resolver;

    public PluginLoadContext(FileInfo pluginFile) {
        _resolver = new AssemblyDependencyResolver(pluginFile.FullName);
    }

    protected override Assembly? Load(AssemblyName assemblyName) {
        var assemblyPath = _resolver.ResolveAssemblyToPath(assemblyName);
        return assemblyPath != null ? LoadFromAssemblyPath(assemblyPath) : null;
    }

    protected override IntPtr LoadUnmanagedDll(string unmanagedDllName) {
        var libraryPath = _resolver.ResolveUnmanagedDllToPath(unmanagedDllName);
        return libraryPath != null ? LoadUnmanagedDllFromPath(libraryPath) : IntPtr.Zero;
    }
}