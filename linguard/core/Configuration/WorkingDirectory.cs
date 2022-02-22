using Linguard.Core.Models.Wireguard;

namespace Linguard.Core.Configuration; 

public sealed class WorkingDirectory : IWorkingDirectory {

    public DirectoryInfo BaseDirectory { get; set; }
    private DirectoryInfo InterfacesDirectory => new(Path.Combine(BaseDirectory.FullName, "interfaces"));

    private const string WireguardConfigurationFileExtension = "conf";
    
    public FileInfo GetInterfaceConfigurationFile(Interface @interface) =>
        new(Path.ChangeExtension(Path.Combine(InterfacesDirectory.FullName, @interface.Name), 
            WireguardConfigurationFileExtension));
}