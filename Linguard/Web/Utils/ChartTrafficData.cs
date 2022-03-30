using ByteSizeLib;

namespace Linguard.Web.Utils; 

public record ChartTrafficData {
    public string Key { get; init; }
    public ByteSize Value { get; init; }
    
    public DateTime DateTime { get; init; }

    public override string ToString() {
        return $"{Key}: {Value.Format()}";
    }
}