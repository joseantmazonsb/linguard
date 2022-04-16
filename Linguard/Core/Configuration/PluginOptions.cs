namespace Linguard.Core.Configuration;
public class PluginOptions : IPluginOptions {
    public DirectoryInfo PluginsDirectory { get; set; }
    
    public object Clone() {
        return MemberwiseClone();
    }
}