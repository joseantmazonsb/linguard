namespace Linguard.Core.Services; 

public interface IEncryptionService {
    Stream Encrypt(FileInfo file);
    Stream Decrypt(FileInfo file);
}