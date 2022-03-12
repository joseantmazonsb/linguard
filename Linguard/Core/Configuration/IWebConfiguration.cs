namespace Linguard.Core.Configuration; 

public interface IWebConfiguration : ICloneable {
    public int LoginAttempts { get; set; }
    public string SecretKey { get; set; }
}