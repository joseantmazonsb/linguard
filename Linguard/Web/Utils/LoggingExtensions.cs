using NLog.Extensions.Logging;
using NLog.Web;

namespace Linguard.Web.Utils; 

public static class LoggingExtensions {
    public static ILoggingBuilder UseNlog(this ILoggingBuilder builder) {
        builder.ClearProviders();
        NLog.LogManager.Setup().LoadConfigurationFromAppSettings();
        builder.AddNLog();
        return builder;
    }
}