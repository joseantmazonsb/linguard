using Linguard.Core.Configuration.Exceptions;
using Linguard.Core.Managers;
using Linguard.Core.Utils;
using Linguard.Log;
using Typin;

namespace Linguard.Cli.Middlewares; 

public class ConfigurationSetupMiddleware : IMiddleware {
    private readonly IConfigurationManager _configurationManager;
    private readonly ILogger _logger;

    private static readonly string WorkingDirectoryEnvironmentVariable = $"{AssemblyInfo.Product}Workdir";

    public ConfigurationSetupMiddleware(IConfigurationManager configurationManager, ILogger logger) {
        _configurationManager = configurationManager;
        _logger = logger;
    }

    public async Task HandleAsync(ICliContext context, CommandPipelineHandlerDelegate next, 
        CancellationToken cancellationToken) {
        if (_configurationManager.WorkingDirectory.BaseDirectory != default) {
            return;
        }
        _configurationManager.WorkingDirectory.BaseDirectory = GetWorkingDirectory(context);
        _logger.Info("Loading configuration...");
        try {
            _configurationManager.Load();
            _logger.Info("Configuration loaded.");
        }
        catch (ConfigurationNotLoadedError e) {
            _logger.Warn(e, "Unable to load configuration. Using defaults.");
            _configurationManager.LoadDefaults();
        }
        await next.Invoke();
    }

    private static DirectoryInfo GetWorkingDirectory(ICliContext context) {
        DirectoryInfo workingDirectory;
        try {
            workingDirectory = new DirectoryInfo(context.EnvironmentVariables[WorkingDirectoryEnvironmentVariable]);
            context.Console.Output.WriteLine($"Using '{workingDirectory.FullName}' as working directory...");
        }
        catch {
            workingDirectory = new DirectoryInfo(Path.GetFullPath("."));
            var warn = "WARNING: No working directory specified through environment variable " +
                       $"'{WorkingDirectoryEnvironmentVariable}'. " +
                       $"The current directory, '{workingDirectory}', will be used instead.";
            context.Console.ForegroundColor = ConsoleColor.Yellow;
            context.Console.Output.WriteLine(warn);
            context.Console.ResetColor();
        }
        workingDirectory.Create();
        return workingDirectory;
    }
}