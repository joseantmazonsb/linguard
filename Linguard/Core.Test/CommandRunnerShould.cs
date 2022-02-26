using FluentAssertions;
using Linguard.Core.OS;
using Xunit;

namespace Core.Test; 

public class CommandRunnerShould {
    [Fact]
    public void RunSingleCommand() {
        var result = new CommandRunner().Run("gci");
        result.Success.Should().BeTrue();
        result.Stdout.Should().NotBeEmpty();
        result.Stderr.Should().BeEmpty();
    }
    
    [Fact]
    public void RunPipedCommands() {
        var result = new CommandRunner().Run("gci | sort-object -Property Name");
        result.Success.Should().BeTrue();
        result.Stdout.Should().NotBeEmpty();
        result.Stderr.Should().BeEmpty();
    }
    
    [Fact]
    public void RunCommandsWithoutPiping() {
        var result = new CommandRunner().Run("gci; get-process");
        result.Success.Should().BeTrue();
        result.Stdout.Should().NotBeEmpty();
        result.Stderr.Should().BeEmpty();
    }
}