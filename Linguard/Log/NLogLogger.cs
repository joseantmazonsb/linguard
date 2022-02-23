using System.Diagnostics;
using NLog;

namespace Linguard.Log; 

public class NLogLogger : LoggerBase {

    private static readonly Logger Logger = LogManager.GetCurrentClassLogger();

    private static void DoLog(LogLevel level, string message, object[] args) {
        var nlogLevel = NLog.LogLevel.FromString(level.ToString());
        var stackTrace = new StackTrace();
        var caller = stackTrace.GetFrame(3)?.GetMethod()?.DeclaringType;
        var logEventInfo = new LogEventInfo(nlogLevel, caller?.Name, null, message, args);
        var wrapper = stackTrace.GetFrame(2)?.GetMethod()?.DeclaringType;
        Logger.Log(wrapper, logEventInfo);
    }
    
    public override void Log(LogLevel level, string message) {
        DoLog(level, message, Array.Empty<object>());
    }
    public override void Log(LogLevel level, Exception exception, string message) {
        DoLog(level, message, new object[] {exception});
    }

    public override bool IsEnabled(LogLevel level) {
        return Logger.IsEnabled(NLog.LogLevel.FromString(level.ToString()));
    }
}