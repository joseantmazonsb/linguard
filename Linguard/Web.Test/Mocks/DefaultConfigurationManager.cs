using Core.Test.Mocks;
using Linguard.Core.Configuration;
using Linguard.Web.Configuration;
using Moq;

namespace Web.Test.Mocks; 

public class DefaultConfigurationManager : Mock<IConfigurationManager> {
    public DefaultConfigurationManager() {
        var configuration = new DefaultConfiguration().Object;
        configuration.Traffic.StorageDriver.Initialize(Object);
        SetupProperty(c => c.Configuration, configuration);
        SetupProperty(c => c.PluginEngine, new PluginEngineMock().Object);
    }
}