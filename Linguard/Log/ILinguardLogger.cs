using Microsoft.Extensions.Logging;

namespace Linguard.Log; 

public interface ILinguardLogger : ILogger {
    LogLevel LogLevel { get; set; }
    ILogTarget Target { get; set; }
    string DateTimeFormat { get; set; }
}