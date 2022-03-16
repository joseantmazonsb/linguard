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
        var message = $"{DateTime.Now.ToString(DateTimeFormat)} [{logLevel.ToString().ToUpper()}] " +
                      $"{formatter(state, exception)}";
        if (exception != default) message += $"{Environment.NewLine}The following exception was raised:" +
                                             $"{Environment.NewLine}{exception}";
        Target?.WriteLine(message);
    }

    public bool IsEnabled(LogLevel logLevel) {
        return logLevel >= LogLevel;
    }

    public IDisposable BeginScope<TState>(TState state) => default!;

}

public static class Extensions {
    public static ILoggingBuilder AddSimpleFileLogger(this ILoggingBuilder builder) {
        var logger = new SimpleFileLogger();
        builder.Services.TryAddSingleton<ILogger>(logger);
        builder.Services.TryAddSingleton<ILinguardLogger>(logger);
        return builder;
    }
    
    public static ILoggingBuilder UseSimpleFileLogger(this ILoggingBuilder builder) {
        builder.ClearProviders();
        return AddSimpleFileLogger(builder);
    }
}