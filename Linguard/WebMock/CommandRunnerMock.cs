using Linguard.Core.OS;
using Moq;

namespace WebMock; 

public class CommandRunnerMock : Mock<ICommandRunner> {
    public CommandRunnerMock() {
        Setup(o => o.Run(It.IsAny<string>()))
            .Returns(new CommandResult(string.Empty, string.Empty, true));
    }
}