using System.Net.NetworkInformation;
using YamlDotNet.Core;
using YamlDotNet.Core.Events;
using YamlDotNet.Serialization;

namespace Linguard.Core.Configuration.Serialization; 

public class NetworkInterfaceTypeConverter : IYamlTypeConverter {
    public bool Accepts(Type type) {
        return type == typeof(NetworkInterface) || type.BaseType == typeof(NetworkInterface);
    }

    public object? ReadYaml(IParser parser, Type type) {
        var value = (parser.Current as Scalar)?.Value;
        parser.MoveNext();
        return string.IsNullOrEmpty(value) 
            ? default 
            : NetworkInterface.GetAllNetworkInterfaces()
                .First(i => i.Name == value);
    }

    public void WriteYaml(IEmitter emitter, object? value, Type type) {
        var @interface = (value as NetworkInterface)?.Name;
        emitter.Emit(new Scalar(null, @interface ?? string.Empty));
    }
}