using YamlDotNet.Core;
using YamlDotNet.Core.Events;
using YamlDotNet.Serialization;

namespace Linguard.Core.Configuration.Serialization; 

public class UriTypeConverter : IYamlTypeConverter {
    public bool Accepts(Type type) {
        return type == typeof(Uri);
    }

    public object? ReadYaml(IParser parser, Type type) {
        var value = (parser.Current as Scalar)?.Value;
        var uri = string.IsNullOrEmpty(value) ? default : new Uri(value, UriKind.RelativeOrAbsolute);
        parser.MoveNext();
        return uri;
    }

    public void WriteYaml(IEmitter emitter, object? value, Type type) {
        var uri = (value as Uri)?.ToString();
        emitter.Emit(new Scalar(null, uri ?? string.Empty));
    }
}