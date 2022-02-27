using Linguard.Core.Managers;
using Linguard.Web.Services;
using Moq;

namespace WebMock;

public class LifetimeServiceMock : Mock<ILifetimeService> {
    public LifetimeServiceMock(IConfigurationManager manager) {
        Setup(o => o.OnAppStarted()).Callback(manager.LoadDefaults);
    }
}