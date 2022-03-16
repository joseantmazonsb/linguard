using Linguard.Core.Models.Wireguard;

namespace Linguard.Web.Helpers; 

public interface IWebHelper {
    Task Download(string data, string filename);
    Task DownloadConfiguration();
    Task DownloadWireguardModel(IWireguardPeer peer);
    void RemoveWireguardModel(IWireguardPeer peer);
    byte[] GetQrCode(IWireguardPeer peer);
}