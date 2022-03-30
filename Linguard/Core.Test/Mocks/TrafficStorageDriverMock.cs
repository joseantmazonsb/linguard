using System;
using System.Collections.Generic;
using Linguard.Core.Drivers.TrafficStorage;
using Moq;

namespace Core.Test.Mocks; 

public class TrafficStorageDriverMock : Mock<ITrafficStorageDriver> {
    public TrafficStorageDriverMock(string name, string description) {
        SetupGet(d => d.Name).Returns(name);
        SetupGet(d => d.Description).Returns(description);
        SetupProperty(d => d.CollectionInterval, TimeSpan.FromHours(1));
        SetupProperty(d => d.AdditionalOptions, new Dictionary<string, string>());
    }
}