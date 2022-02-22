using Linguard.Core.Configuration;
using Linguard.Core.Configuration.Serialization;
using Linguard.Core.Utils;

namespace Linguard.Core.Managers; 

public class YamlConfigurationManager : FileConfigurationManager {
    private static readonly string[] SupportedExtensions = {"yaml", "yml"};

    private FileInfo? _configurationFile;
    protected sealed override FileInfo ConfigurationFile {
        get {
            if (_configurationFile != default) return _configurationFile;
            var filename = Path.Combine(WorkingDirectory.BaseDirectory.FullName, AssemblyInfo.Product.ToLower());
            var tries = 0;
            while (tries < SupportedExtensions.Length && _configurationFile is not { Exists: true }) {
                var filepath = Path.ChangeExtension(filename, SupportedExtensions[tries]);
                _configurationFile = new FileInfo(filepath);
                tries++;
            }
            return _configurationFile!;
        }
    }

    public override void LoadDefaults() {
        // Ignore
    }

    public YamlConfigurationManager(IConfiguration configuration, IWorkingDirectory workingDirectory) 
        : base(configuration, workingDirectory, new YamlConfigurationSerializer()) {
    }
}