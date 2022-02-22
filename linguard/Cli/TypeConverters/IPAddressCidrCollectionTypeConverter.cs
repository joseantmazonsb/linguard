using Linguard.Core;
using Typin.Binding;

namespace Linguard.Cli.TypeConverters; 

public class IPAddressCidrCollectionTypeConverter : BindingConverter<ICollection<IPAddressCidr>> {

    public override ICollection<IPAddressCidr>? Convert(string? value) {
        throw new NotImplementedException();
    }

    public override ICollection<IPAddressCidr> ConvertCollection(IReadOnlyCollection<string> values) {
        return values.Select(IPAddressCidr.Parse).ToList();
    }
}