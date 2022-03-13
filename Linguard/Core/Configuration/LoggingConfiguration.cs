using Microsoft.Extensions.Logging;

namespace Linguard.Core.Configuration; 

public class LoggingConfiguration : ILoggingConfiguration {
    public LogLevel Level { get; set; }
    public string DateTimeFormat { get; set; }

    public object Clone() {
        return MemberwiseClone();
    }
}