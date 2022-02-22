using System.Net.NetworkInformation;
using Typin.Binding;

namespace Linguard.Cli.TypeConverters; 

public class NetworkInterfaceTypeConverter : BindingConverter<NetworkInterface> {

    public override NetworkInterface? Convert(string? value) {
        return value != default
            ? NetworkInterface
                .GetAllNetworkInterfaces()
                .SingleOrDefault(i =>
                    i.Name.Equals(value, StringComparison.OrdinalIgnoreCase))
            : default;
    }

    public override NetworkInterface ConvertCollection(IReadOnlyCollection<string> values) {
        throw new NotImplementedException();
    }
}