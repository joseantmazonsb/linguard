using Core.Test.Stubs;
using Linguard.Core.Plugins;
using Moq;

namespace Core.Test.Mocks; 

public class PluginEngineMock : Mock<IPluginEngine> {
    public PluginEngineMock() {
        SetupGet(p => p.Plugins).Returns(new[] {
            new TrafficStorageDriverStub(),
            new TrafficStorageDriverMock("Mock driver", "This is a mocked driver").Object,
            new TrafficStorageDriverMock("Mock driver 2", "This is another mocked driver").Object
        });
    }
}