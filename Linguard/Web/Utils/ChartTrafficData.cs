using ByteSizeLib;

namespace Linguard.Web.Utils; 

public class ChartTrafficData {
    public string Key { get; init; }
    public ByteSize Value { get; init; }

    public override string ToString() {
        return $"{Key}: {Value.Format()}";
    }
}