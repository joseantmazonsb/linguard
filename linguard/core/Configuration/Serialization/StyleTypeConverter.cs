using Linguard.Core.Models;
using YamlDotNet.Core;
using YamlDotNet.Core.Events;
using YamlDotNet.Serialization;

namespace Linguard.Core.Configuration.Serialization; 

public class StyleTypeConverter : IYamlTypeConverter {
    public bool Accepts(Type type) {
        return type == typeof(Style);
    }

    public object? ReadYaml(IParser parser, Type type) {
        var value = (parser.Current as Scalar)?.Value;
        var style = string.IsNullOrEmpty(value) ? default : Enum.Parse<Style>(value, true);
        parser.MoveNext();
        return style;
    }

    public void WriteYaml(IEmitter emitter, object? value, Type type) {
        emitter.Emit(new Scalar(null, value?.ToString() ?? string.Empty));
    }
}