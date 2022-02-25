using System;
using System.Net.NetworkInformation;
using Moq;
using YamlDotNet.Core;
using YamlDotNet.Core.Events;
using YamlDotNet.Serialization;

namespace Core.Test.Mocks; 

public class NetworkInterfaceTypeConverterMock : IYamlTypeConverter {
    public bool Accepts(Type type) {
        return type == typeof(NetworkInterface) || type.BaseType == typeof(NetworkInterface);
    }

    public object? ReadYaml(IParser parser, Type type) {
        var value = (parser.Current as Scalar)?.Value;
        parser.MoveNext();
        if (string.IsNullOrEmpty(value)) return default;
        var mock = new Mock<NetworkInterface>();
        mock.SetupGet(i => i.Name).Returns(value);
        return mock.Object;
    }
    
    public void WriteYaml(IEmitter emitter, object? value, Type type) {
        var @interface = (value as NetworkInterface)?.Name;
        emitter.Emit(new Scalar(null, @interface ?? string.Empty));
    }
}