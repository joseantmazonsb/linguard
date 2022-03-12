using Linguard.Core.Exceptions;
using Linguard.Core.Utils;

namespace Linguard.Core.Services.Exceptions; 

public class WireguardException : ExtendedException {

    private static readonly string[] _fixes = {
        "Verify that your Wireguard settings are correct.",
        $"Ensure the user running {AssemblyInfo.Product} is able to run Wireguard as super user."
    };

    public WireguardException(string message) : base(message) {}
    public WireguardException(string message, Exception innerException) : base(message, innerException) {}

    public override IEnumerable<string> Fixes => _fixes;
}