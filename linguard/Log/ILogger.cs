namespace Linguard.Log;

public interface ILogger {
    void Log(LogLevel level, string message);
    void Log(LogLevel level, Exception exception, string message);
    
    void Trace(string message);
    void Trace(Exception exception, string message);
    
    void Debug(string message);
    void Debug(Exception exception, string message);
    
    void Info(string message);
    void Info(Exception exception, string message);
    
    void Warn(string message);
    void Warn(Exception exception, string message);
    
    void Error(string message);
    void Error(Exception exception, string message);
    
    void Fatal(string message);
    void Fatal(Exception exception, string message);

    bool IsEnabled(LogLevel level);
    bool IsTraceEnabled(LogLevel level);
    bool IsDebugEnabled(LogLevel level);
    bool IsInfoEnabled(LogLevel level);
    bool IsWarnEnabled(LogLevel level);
    bool IsErrorEnabled(LogLevel level);
    bool IsFatalEnabled(LogLevel level);
}