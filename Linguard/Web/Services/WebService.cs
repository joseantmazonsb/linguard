using System.Text;
using Linguard.Core.Configuration;
using Linguard.Core.Managers;
using Linguard.Core.Models.Wireguard;
using Linguard.Core.Services;
using Linguard.Core.Utils;
using Microsoft.JSInterop;
using QRCoder;

namespace Linguard.Web.Services; 

public class WebService : IWebService {
    
    public WebService(IJSRuntime jsRuntime, IWireguardService wireguardService, 
        IConfigurationManager configurationManager, QRCodeGenerator qrCodeGenerator, IInterfaceService interfaceService) {
        JsRuntime = jsRuntime;
        WireguardService = wireguardService;
        ConfigurationManager = configurationManager;
        QrCodeGenerator = qrCodeGenerator;
        InterfaceService = interfaceService;
    }

    private IJSRuntime JsRuntime { get; }
    private IWireguardService WireguardService { get; }
    private IInterfaceService InterfaceService { get; }
    private IConfigurationManager ConfigurationManager { get; }
    private IWireguardConfiguration Configuration => ConfigurationManager.Configuration.Wireguard;
    private QRCodeGenerator QrCodeGenerator {get; }

    public async Task Download(string data, string filename) {
        var bytes = Encoding.UTF8.GetBytes(data);
        var fileStream = new MemoryStream(bytes);
        using var streamRef = new DotNetStreamReference(fileStream);
        await JsRuntime.InvokeVoidAsync("downloadFileFromStream", filename, streamRef);
    }

    public Task DownloadConfiguration() {
        return Download(ConfigurationManager.Export(), $"{AssemblyInfo.Product.ToLower()}.config");
    }

    public Task DownloadWireguardModel(IWireguardPeer peer) {
        return Download(WireguardService.GenerateWireguardConfiguration(peer), $"{peer.Name}.conf");
    }
    
    public void RemoveWireguardModel(IWireguardPeer peer) {
        switch (peer) {
            case Client client:
                RemoveClient(client);
                break;
            case Interface iface:
                RemoveInterface(iface);
                break;
        }
    }

    public byte[] GetQrCode(IWireguardPeer peer) {
        var qrCodeData = QrCodeGenerator.CreateQrCode(
            WireguardService.GenerateWireguardConfiguration(peer), QRCodeGenerator.ECCLevel.Q);
        return new PngByteQRCode(qrCodeData).GetGraphic(20);
    }

    private void RemoveClient(Client client) {
        InterfaceService.GetInterface(client)?.Clients.Remove(client);
        ConfigurationManager.Save();
    }
    
    private void RemoveInterface(Interface iface) {
        Configuration.Interfaces.Remove(iface);
        ConfigurationManager.Save();
    }
}