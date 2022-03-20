using Linguard.Core.Configuration;
using Linguard.Web.Configuration;
using Moq;

namespace Web.Test.Mocks; 

public class DefaultConfigurationManager : Mock<IConfigurationManager> {
    public DefaultConfigurationManager() {
        SetupProperty(c => c.Configuration, new DefaultConfiguration().Object);
        SetupProperty(c => c.WorkingDirectory, new Mock<IWorkingDirectory>().Object);
    }
}