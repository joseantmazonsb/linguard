﻿using System.Net.NetworkInformation;
using Linguard.Core.Models;
using Linguard.Core.Models.Wireguard;

namespace Linguard.Core.Services; 

public interface IWireguardService {
    Interface? GetInterface(Client client);
    void StartInterface(Interface @interface);
    void StopInterface(Interface @interface);
    string? GenerateWireguardPrivateKey();
    string? GenerateWireguardPublicKey(string privateKey);
    string[] GenerateOnUpRules(string interfaceName, NetworkInterface gateway);
    string[] GenerateOnDownRules(string interfaceName, NetworkInterface gateway);
    string GenerateWireguardConfiguration(IWireguardPeer peer);
    DateTime GetLastHandshake(Client client);
    IEnumerable<TrafficData> GetTrafficData();
    IEnumerable<TrafficData> GetTrafficData(Client client);
    IEnumerable<TrafficData> GetTrafficData(Interface iface);
}