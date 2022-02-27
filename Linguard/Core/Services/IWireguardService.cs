﻿using System.Net.NetworkInformation;
using Linguard.Core.Models;
using Linguard.Core.Models.Wireguard;

namespace Linguard.Core.Services; 

public interface IWireguardService {
    Interface? GetInterface(Client client);
    void StartInterface(Interface iface);
    void StopInterface(Interface iface);
    void AddClient(Interface iface, Client client);
    void RemoveClient(Interface iface, Client client);
    string? GenerateWireguardPrivateKey();
    string? GenerateWireguardPublicKey(string privateKey);
    string[] GenerateOnUpRules(string interfaceName, NetworkInterface gateway);
    string[] GenerateOnDownRules(string interfaceName, NetworkInterface gateway);
    string GenerateWireguardConfiguration(IWireguardPeer peer);
    DateTime GetLastHandshake(Client client);
    IEnumerable<TrafficData> GetTrafficData();
    IEnumerable<TrafficData> GetTrafficData(Interface iface);
    TrafficData? GetTrafficData(Client client);
}