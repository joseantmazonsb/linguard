using Linguard.Core.Models.Wireguard;
using YamlDotNet.Core;
using YamlDotNet.Core.Events;
using YamlDotNet.Serialization;

namespace Linguard.Yaml.Serialization; 

public class RuleTypeConverter : IYamlTypeConverter {
    
    public bool Accepts(Type type) {
        return type == typeof(Rule);
    }

    public object? ReadYaml(IParser parser, Type type) {
        var value = parser.Consume<Scalar>().Value;
        return value;
    }

    public void WriteYaml(IEmitter emitter, object? value, Type type) {
        emitter.Emit(new Scalar(null, value?.ToString() ?? string.Empty));
    }
}