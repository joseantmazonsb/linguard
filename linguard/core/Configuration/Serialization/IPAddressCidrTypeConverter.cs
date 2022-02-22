using YamlDotNet.Core;
using YamlDotNet.Core.Events;
using YamlDotNet.Serialization;

namespace Linguard.Core.Configuration.Serialization; 

public class IPAddressCidrTypeConverter : IYamlTypeConverter {
    
    public bool Accepts(Type type) {
        return type == typeof(IPAddressCidr);
    }

    public object? ReadYaml(IParser parser, Type type) {
        var value = (parser.Current as Scalar)?.Value;
        parser.MoveNext();
        return string.IsNullOrEmpty(value) ? default : IPAddressCidr.Parse(value);
    }

    public void WriteYaml(IEmitter emitter, object? value, Type type) {
        var address = (value as IPAddressCidr)?.ToString();
        emitter.Emit(new Scalar(null, address ?? string.Empty));
    }
}