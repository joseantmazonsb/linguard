using Linguard.Core.Models.Wireguard;

namespace Linguard.Core.Configuration;

/// <summary>
/// The root directory for the application, used to store and read data. 
/// </summary>
public interface IWorkingDirectory {
    DirectoryInfo BaseDirectory { get; set; }
    FileInfo GetInterfaceConfigurationFile(Interface @interface);
    string CredentialsPath { get; }
}