using Linguard.Core.Models;

namespace Linguard.Core.Configuration; 

public class WebConfiguration : IWebConfiguration {
    public int LoginAttempts { get; set; } = 10;
    public string SecretKey { get; set; } = string.Empty;
    public Style Style { get; set; }
    
    public object Clone() {
        return MemberwiseClone();
    }
}