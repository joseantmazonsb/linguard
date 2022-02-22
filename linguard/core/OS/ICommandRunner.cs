namespace Linguard.Core.OS; 

public interface ICommandRunner {
    ICommandResult Run(string command);
}