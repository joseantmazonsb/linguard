using System.Configuration;
using System.Text.Json;
using ConfigurationManager = Microsoft.Extensions.Configuration.ConfigurationManager;

namespace Linguard.Web.Utils; 

public static class ConfigurationManagerExtensions {
    public static void SaveConfiguration(this ConfigurationManager manager) {
        var settingsPath = manager.GetFileProvider().GetFileInfo("appsettings.json").PhysicalPath;
        // TODO complete
        // IWebHostEnvironment to know if production 
        // var json = JsonSerializer.Serialize(manager, new JsonSerializerOptions {
        //     WriteIndented = true
        // });
        // File.WriteAllText(filepath, json);
    }
}