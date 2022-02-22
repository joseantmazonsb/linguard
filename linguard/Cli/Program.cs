using Typin;

namespace Linguard.Cli;

public static class Program {
    public static async Task<int> Main() =>
        await new CliApplicationBuilder()
            .UseStartup<CliStartup>()
            .Build()
            .RunAsync();
}