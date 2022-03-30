using System.Text.RegularExpressions;
using ByteSizeLib;
using Linguard.Core.Models;
using Linguard.Core.Models.Wireguard;

namespace Linguard.Core.Utils.Wireguard; 

public static class WireguardDumpParser {
    /// <summary>
    /// Get traffic data for the specified interface and all its clients from a Wireguard dump string.
    /// </summary>
    /// <param name="data"></param>
    /// <param name="iface"></param>
    /// <returns></returns>
    public static IReadOnlySet<TrafficData> GetTrafficData(string data, Interface iface) {
        var trafficData = new HashSet<TrafficData>();
        const StringSplitOptions trimOptions = StringSplitOptions.TrimEntries | StringSplitOptions.RemoveEmptyEntries;
        var timeStamp = DateTime.Now;
        var lines = data
            .Split(Environment.NewLine, trimOptions)
            .Select(l => Regex.Replace(l, @"\s+", " "));
        foreach (var line in lines) {
            var split = line.Split(" ", trimOptions);
            var privateKey = split[2];
            var isClient = privateKey == "(none)";
            if (!isClient) {
                continue;
            }
            var publicKey = split[1];
            var client = iface.Clients.SingleOrDefault(c => c.PublicKey == publicKey);
            if (client == default) {
                continue;
            }
            var entry = new TrafficData {
                Peer = client,
                TimeStamp = timeStamp
            };
            try {
                entry.ReceivedData = ByteSize.FromBytes(long.Parse(split[6]));
            }
            catch (Exception) {
                // Ignore
            }
            try {
                entry.SentData = ByteSize.FromBytes(long.Parse(split[7]));
            }
            catch (Exception) {
                // Ignore
            }
            trafficData.Add(entry);
        }
        trafficData.Add(new TrafficData {
            Peer = iface,
            ReceivedData = ByteSize.FromBytes(trafficData.Sum(e => e.ReceivedData.Bytes)),
            SentData = ByteSize.FromBytes(trafficData.Sum(e => e.SentData.Bytes))
        });
        return trafficData;
    }

    public static DateTime GetLastHandshake(string data, Client client) {
        const StringSplitOptions trimOptions =
            StringSplitOptions.TrimEntries | StringSplitOptions.RemoveEmptyEntries;
        var clientEntry = data
            .Split(Environment.NewLine, trimOptions)
            .SingleOrDefault(l => l.Contains(client.PublicKey));
        var clientInfo = Regex.Replace(clientEntry, @"\s+", " ").Split(" ");
        return DateTime.FromBinary(long.Parse(clientInfo[5]));
    }
}