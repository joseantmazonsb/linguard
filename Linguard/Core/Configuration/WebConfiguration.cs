namespace Linguard.Core.Configuration; 

public class WebConfiguration : IWebConfiguration {
    public int LoginAttempts { get; set; }
    public string SecretKey { get; set; }
    public object Clone() {
        return MemberwiseClone();
    }
}