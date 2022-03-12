using Microsoft.Extensions.Logging;

namespace Linguard.Core.Configuration; 

public interface ILoggingConfiguration : ICloneable {
    public LogLevel Level { get; set; }
}