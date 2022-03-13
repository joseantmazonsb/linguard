using Microsoft.Extensions.DependencyInjection.Extensions;
using Microsoft.Extensions.Logging;

namespace Linguard.Log; 

public class SimpleFileLogger : ILinguardLogger {
    public LogLevel LogLevel { get; set; } = LogLevel.Information;
    public ILogTarget Target { get; set; }
    public string DateTimeFormat { get; set; } = "yyyy-MM-dd HH:mm:ss.fff";
    
    public void Log<TState>(LogLevel logLevel, EventId eventId, TState state, 
        Exception? exception, Func<TState, Exception?, string> formatter) {
        if (!IsEnabled(logLevel)) return;
        Target?.WriteLine($"{DateTime.Now.ToString(DateTimeFormat)} [{logLevel.ToString().ToUpper()}] " +
                         $"{formatter(state, exception)}");
    }

    public bool IsEnabled(LogLevel logLevel) {
        return logLevel >= LogLevel;
    }

    public IDisposable BeginScope<TState>(TState state) => default!;

}

public static class Extensions {
    public static ILoggingBuilder AddSimpleFileLogger(this ILoggingBuilder builder) {
        builder.Services.TryAddSingleton<ILinguardLogger, SimpleFileLogger>();
        return builder;
    }
    
    public static ILoggingBuilder UseSimpleFileLogger(this ILoggingBuilder builder) {
        builder.ClearProviders();
        return AddSimpleFileLogger(builder);
    }
}