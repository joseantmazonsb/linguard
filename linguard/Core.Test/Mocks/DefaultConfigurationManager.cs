using Linguard.Core.Configuration;
using Linguard.Core.Managers;
using Moq;

namespace Core.Test.Mocks; 

public class DefaultConfigurationManager : Mock<IConfigurationManager> {
    public DefaultConfigurationManager() {
        SetupProperty(c => c.Configuration, new DefaultConfiguration().Object);
        SetupProperty(c => c.WorkingDirectory, new Mock<IWorkingDirectory>().Object);
    }
}