namespace Linguard.Core.OS; 

public class CommandResult : ICommandResult {
    public CommandResult(string stdout, string stderr, bool success) {
        Stdout = stdout;
        Stderr = stderr;
        Success = success;
    }

    public string Stdout { get; }
    public string Stderr { get; }
    public bool Success { get; }
}