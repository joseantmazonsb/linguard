using System.Globalization;
using YamlDotNet.Core;
using YamlDotNet.Core.Events;
using YamlDotNet.Serialization;

namespace Linguard.Yaml.Serialization; 

public class TimeSpanTypeConverter : IYamlTypeConverter {
    public bool Accepts(Type type) {
        return type == typeof(TimeSpan);
    }

    public object? ReadYaml(IParser parser, Type type) {
        var value = (parser.Current as Scalar)?.Value;
        if (!int.TryParse(value, out var intValue)) {
            return default;
        }
        var timeSpan = string.IsNullOrEmpty(value) ? default : TimeSpan.FromSeconds(intValue);
        parser.MoveNext();
        return timeSpan;
    }

    public void WriteYaml(IEmitter emitter, object? value, Type type) {
        var seconds = ((TimeSpan)(value ?? 0)).TotalSeconds;
        emitter.Emit(new Scalar(null, seconds.ToString(CultureInfo.InvariantCulture)));
    }
}