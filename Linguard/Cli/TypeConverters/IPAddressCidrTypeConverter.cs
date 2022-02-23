using Linguard.Core;
using Typin.Binding;

namespace Linguard.Cli.TypeConverters; 

public class IPAddressCidrTypeConverter : BindingConverter<IPAddressCidr> {

    public override IPAddressCidr? Convert(string? value) {
        return value != default 
            ? IPAddressCidr.Parse(value)
            : default;
    }

    public override IPAddressCidr ConvertCollection(IReadOnlyCollection<string> values) {
        throw new NotImplementedException();
    }
}