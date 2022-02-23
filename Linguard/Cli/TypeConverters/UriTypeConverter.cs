using Typin.Binding;

namespace Linguard.Cli.TypeConverters; 

public class UriTypeConverter : BindingConverter<Uri> {
    public override Uri? Convert(string? value) {
        return value != default 
            ? new Uri(value, UriKind.RelativeOrAbsolute) 
            : default;
    }

    public override Uri ConvertCollection(IReadOnlyCollection<string> values) {
        throw new NotImplementedException();
    }
}