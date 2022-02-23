using System.Management.Automation;

namespace Linguard.Core.OS; 

public class CommandRunner : ICommandRunner {

    public ICommandResult Run(string command) {
        var ps = PowerShell.Create();
        var results = ps.AddScript(command).Invoke();
        var stdout = string.Join(Environment.NewLine, results);
        var stderr = string.Join(Environment.NewLine, ps.Streams.Error);
        return new CommandResult(stdout, stderr, !ps.HadErrors);
    }
}