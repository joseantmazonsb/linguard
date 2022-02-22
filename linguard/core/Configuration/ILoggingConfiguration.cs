using Linguard.Log;

namespace Linguard.Core.Configuration; 

public interface ILoggingConfiguration : ICloneable {
    public LogLevel Level { get; set; }
    public bool Overwrite { get; set; }
}