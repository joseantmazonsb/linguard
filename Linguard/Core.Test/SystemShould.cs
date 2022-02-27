using Core.Test.Mocks;
using FluentAssertions;
using Linguard.Core.Managers;
using Linguard.Core.OS;
using Moq;
using Xunit;

namespace Core.Test; 

public class SystemShould {
    
    private static readonly Mock<IConfigurationManager> ConfigurationManagerMock = new DefaultConfigurationManager();
    private readonly ISystemWrapper _systemWrapper = new SystemWrapper(ConfigurationManagerMock.Object);
    
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