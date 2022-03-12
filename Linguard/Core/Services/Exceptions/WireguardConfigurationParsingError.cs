using Linguard.Core.Exceptions;

namespace Linguard.Core.Services.Exceptions; 

public class WireguardConfigurationParsingError : ExtendedException {

    public WireguardConfigurationParsingError(string message) : base(message) {
        
    }
    
    private readonly string[] _fixes = {
        "Verify that the Wireguard configuration file is correct."
    };

    public override IEnumerable<string> Fixes => _fixes;
}