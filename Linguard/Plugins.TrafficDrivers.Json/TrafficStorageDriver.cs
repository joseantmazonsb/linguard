using System.Text.Json;
using Linguard.Core.Configuration;
using Linguard.Core.Drivers.TrafficStorage;
using Linguard.Core.Models;

namespace Linguard.Plugins.TrafficDrivers.Json;

public class TrafficStorageDriver : TrafficStorageDriverBase {

    private const string FileName = "traffic";
    private const string FileExtension = "json";
    private const string DateTimeFormat = "yyyy-MM-dd HH:mm:ss";

    private IWireguardOptions WireguardOptions => 
        ConfigurationManager!.Configuration.Wireguard;
    private JsonSerializerOptions SerializerOptions 
        => TrafficDataSerializerOptions.Build(WireguardOptions, DateTimeFormat);
    
    private DirectoryInfo Directory => ConfigurationManager!.Configuration.Plugins.PluginsDirectory;
    
    private FileInfo File => new(Path.ChangeExtension(Path.Combine(Directory.FullName, FileName), FileExtension));
    
    public override string Name => "Json";
    public override string Description => "Driver that stores traffic data in JSON format.";

    public override void Save(IEnumerable<ITrafficData> data) {
        var fullData = Load().Concat(data);
        using var writer = new StreamWriter(File.Open(FileMode.Append));
        var json = JsonSerializer.Serialize(fullData, SerializerOptions);
        writer.Write(json);
    }
    
    public override IEnumerable<ITrafficData> Load() {
        using var reader = new StreamReader(File.OpenRead());
        var existingJsonData = reader.ReadToEnd();
        return JsonSerializer.Deserialize<IEnumerable<ITrafficData>>(existingJsonData, SerializerOptions) 
               ?? new List<ITrafficData>();
    }

    public override object Clone() {
        var clone = new TrafficStorageDriver {
            CollectionInterval = CollectionInterval,
            AdditionalOptions = new Dictionary<string, string>(AdditionalOptions)
        };
        clone.Initialize(ConfigurationManager);
        return clone;
    }
}