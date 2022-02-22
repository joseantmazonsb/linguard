namespace Linguard.Core.OS; 

public interface ICommandResult {
    string Stdout { get; }
    string Stderr { get; }
    bool Success { get; }
}