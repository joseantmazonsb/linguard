namespace Linguard.Log; 

public abstract class LoggerBase : ILogger {
    public abstract void Log(LogLevel level, string message);
    public abstract void Log(LogLevel level, Exception exception, string message);

    public void Trace(string message) {
        Log(LogLevel.Trace, message);
    }

    public void Trace(Exception exception, string message) {
        Log(LogLevel.Trace, exception, message);
    }

    public void Debug(string message) {
        Log(LogLevel.Debug, message);
    }

    public void Debug(Exception exception, string message) {
        Log(LogLevel.Debug, exception, message);
    }
    
    public void Info(string message) {
        Log(LogLevel.Info, message);
    }

    public void Info(Exception exception, string message) {
        Log(LogLevel.Info, exception, message);
    }

    public void Warn(string message) {
        Log(LogLevel.Warn, message);
    }

    public void Warn(Exception exception, string message) {
        Log(LogLevel.Warn, exception, message);
    }

    public void Error(string message) {
        Log(LogLevel.Error, message);
    }

    public void Error(Exception exception, string message) {
        Log(LogLevel.Error, exception, message);
    }

    public void Fatal(string message) {
        Log(LogLevel.Fatal, message);
    }

    public void Fatal(Exception exception, string message) {
        Log(LogLevel.Fatal, exception, message);
    }

    public abstract bool IsEnabled(LogLevel level);

    public bool IsTraceEnabled(LogLevel level) {
        return IsEnabled(LogLevel.Trace);
    }

    public bool IsDebugEnabled(LogLevel level) {
        return IsEnabled(LogLevel.Debug);
    }

    public bool IsInfoEnabled(LogLevel level) {
        return IsEnabled(LogLevel.Info);
    }

    public bool IsWarnEnabled(LogLevel level) {
        return IsEnabled(LogLevel.Warn);
    }

    public bool IsErrorEnabled(LogLevel level) {
        return IsEnabled(LogLevel.Error);
    }

    public bool IsFatalEnabled(LogLevel level) {
        return IsEnabled(LogLevel.Fatal);
    }
}