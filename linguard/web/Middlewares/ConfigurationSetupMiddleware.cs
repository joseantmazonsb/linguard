using Linguard.Core.Configuration.Exceptions;
using Linguard.Core.Managers;
using Linguard.Core.Utils;
using ILogger = Linguard.Log.ILogger;

namespace Linguard.Web.Middlewares; 

public class ConfigurationSetupMiddleware : IMiddleware {
    private readonly IConfigurationManager _configurationManager;
    private readonly ILogger _logger;

    private static readonly string WorkingDirectoryEnvironmentVariable = $"{AssemblyInfo.Product}Workdir";

    public ConfigurationSetupMiddleware(IConfigurationManager configurationManager, ILogger logger) {
        _configurationManager = configurationManager;
        _logger = logger;
    }

    public async Task InvokeAsync(HttpContext context, RequestDelegate next) {
        if (_configurationManager.WorkingDirectory.BaseDirectory != default) {
            await next.Invoke(context);
            return;
        }
        _configurationManager.WorkingDirectory.BaseDirectory = GetWorkingDirectory();
        _logger.Info("Loading configuration...");
        try {
            _configurationManager.Load();
            _logger.Info("Configuration loaded.");
        }
        catch (ConfigurationNotLoadedError e) {
            _logger.Warn(e, "Unable to load configuration. Using defaults.");
            _configurationManager.LoadDefaults();
        }
        await next.Invoke(context);
    }

    private DirectoryInfo GetWorkingDirectory() {
        DirectoryInfo workingDirectory;
        if (Environment.GetEnvironmentVariables()[WorkingDirectoryEnvironmentVariable] is string workdir) {
            workingDirectory = new DirectoryInfo(workdir);
            _logger.Info($"Using '{workingDirectory.FullName}' as working directory...");
        }
        else {
            workingDirectory = new DirectoryInfo(Path.GetFullPath("."));
            var warn = "WARNING: No working directory specified through environment variable " +
                       $"'{WorkingDirectoryEnvironmentVariable}'. " +
                       $"The current directory, '{workingDirectory}', will be used instead.";
            _logger.Warn(warn);
        }
        workingDirectory.Create();
        return workingDirectory;
    }
}