using ByteSizeLib;

namespace Linguard.Web.Utils; 

public class ChartTrafficData {
    public string Key { get; init; }
    public ByteSize Value { get; init; }

    public override string ToString() {
        var bytes = Value.Bytes;
        if (bytes > ByteSize.BytesInPetaByte) {
            return $"{Key}: {Value.PetaBytes.ToString("0.00")} {ByteSize.PetaByteSymbol}";
        }
        if (bytes > ByteSize.BytesInTeraByte) {
            return $"{Key}: {Value.TeraBytes.ToString("0.00")} {ByteSize.TeraByteSymbol}";
        }
        if (bytes > ByteSize.BytesInGigaByte) {
            return $"{Key}: {Value.GigaBytes.ToString("0.00")} {ByteSize.GigaByteSymbol}";
        }
        if (bytes > ByteSize.BytesInMegaByte) {
            return $"{Key}: {Value.MegaBytes.ToString("0.00")} {ByteSize.MegaByteSymbol}";
        }
        if (bytes > ByteSize.BytesInKiloByte) {
            return $"{Key}: {Value.KiloBytes.ToString("0.00")} {ByteSize.KiloByteSymbol}";
        }
        return $"{Key}: {bytes.ToString("0.00")} {ByteSize.ByteSymbol}";
    }
}