using Linguard.Core.Models.Wireguard;

namespace Linguard.Web.Services; 

public interface IWebService {
    Task Download(string data, string filename);
    Task DownloadConfiguration();
    Task DownloadWireguardModel(IWireguardPeer peer);
    void RemoveWireguardModel(IWireguardPeer peer);
    byte[] GetQrCode(IWireguardPeer peer);
}