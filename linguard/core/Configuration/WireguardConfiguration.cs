using Linguard.Core.Models.Wireguard;
using Linguard.Core.OS;

namespace Linguard.Core.Configuration; 

public class WireguardConfiguration : IWireguardConfiguration {
    public HashSet<Interface> Interfaces { get; set; } = new();
    public string IptablesBin { get; set; } = new CommandRunner()
        .Run("whereis iptables | tr ' ' '\n' | grep bin").Stdout;
    public string WireguardBin { get; set; } = new CommandRunner()
        .Run("whereis wg | tr ' ' '\n' | grep bin").Stdout;
    public string WireguardQuickBin { get; set; } = new CommandRunner()
        .Run("whereis wg-quick | tr ' ' '\n' | grep bin").Stdout;

    public Uri? PrimaryDns { get; set; } = new("8.8.8.8", UriKind.RelativeOrAbsolute);
    public Uri? SecondaryDns { get; set; } = new("8.8.4.4", UriKind.RelativeOrAbsolute);
    public Uri? Endpoint { get; set; } = PublicIP != default 
        ? new(PublicIP, UriKind.RelativeOrAbsolute) 
        : default;

    private static readonly string? PublicIP = default;
    
    private static async Task<string> GetPublicIPAddress() {
        const string url = "https://api.ipify.org/";
        var response = await new HttpClient()
            .Send(new HttpRequestMessage(HttpMethod.Get, url))
            .Content
            .ReadAsStringAsync();
        return response;
    }
        
    public object Clone() {
        return MemberwiseClone();
    }
}