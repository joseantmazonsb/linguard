using System.Net;

namespace Linguard.Core.Utils; 

public static class Network {
    public static IPAddress? GetPublicIPAddress() {
        const string url = "https://api.ipify.org/";
        var response = new HttpClient()
            .Send(new HttpRequestMessage(HttpMethod.Get, url))
            .Content
            .ReadAsStringAsync().Result;
        return IPAddress.TryParse(response, out var ipAddress) ? ipAddress : default;
    }
}