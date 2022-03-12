using ByteSizeLib;

namespace Linguard.Web.Utils; 

public static class FileSize {
    public static string Format(this ByteSize size) {
        var bytes = size.Bytes;
        return bytes switch {
            > ByteSize.BytesInPetaByte => $"{size.PetaBytes:0.00} {ByteSize.PetaByteSymbol}",
            > ByteSize.BytesInTeraByte => $"{size.TeraBytes:0.00} {ByteSize.TeraByteSymbol}",
            > ByteSize.BytesInGigaByte => $"{size.GigaBytes:0.00} {ByteSize.GigaByteSymbol}",
            > ByteSize.BytesInMegaByte => $"{size.MegaBytes:0.00} {ByteSize.MegaByteSymbol}",
            > ByteSize.BytesInKiloByte => $"{size.KiloBytes:0.00} {ByteSize.KiloByteSymbol}",
            _ => $"{bytes:0.00} {ByteSize.ByteSymbol}"
        };
    }
}