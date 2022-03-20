using Microsoft.Extensions.Logging;

namespace Linguard.Core.Configuration; 

public interface ILoggingConfiguration : IConfigurationModule {
    public LogLevel Level { get; set; }
    public string DateTimeFormat { get; set; }
}