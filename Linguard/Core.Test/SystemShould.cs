using FluentAssertions;
using Linguard.Core.OS;
using Xunit;

namespace Core.Test; 

public class SystemShould {
    
    private readonly ISystemWrapper _systemWrapper = new SystemWrapper();
    
    [Fact]
    public void RunSingleCommand() {
        var result = _systemWrapper.RunCommand("gci");
        result.Success.Should().BeTrue();
        result.Stdout.Should().NotBeEmpty();
        result.Stderr.Should().BeEmpty();
    }
    
    [Fact]
    public void RunPipedCommands() {
        var result = _systemWrapper.RunCommand("gci | sort-object -Property Name");
        result.Success.Should().BeTrue();
        result.Stdout.Should().NotBeEmpty();
        result.Stderr.Should().BeEmpty();
    }
    
    [Fact]
    public void RunCommandsWithoutPiping() {
        var result = _systemWrapper.RunCommand("gci; get-process");
        result.Success.Should().BeTrue();
        result.Stdout.Should().NotBeEmpty();
        result.Stderr.Should().BeEmpty();
    }
}