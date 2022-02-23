using Linguard.Core.Models.Wireguard;

namespace Linguard.Web.Services; 

public interface IWebService {
    void Download(string data, string filename);
    void DownloadConfiguration();
    void DownloadWireguardModel(IWireguardPeer peer);
    void RemoveWireguardModel(IWireguardPeer peer);
    byte[] GetQrCode(IWireguardPeer peer);
}