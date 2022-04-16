namespace Linguard.Web.Configuration; 

public class WebOptions : IWebOptions {
    public int LoginAttempts { get; set; }
    public TimeSpan LoginBanTime { get; set; }
    
    public object Clone() {
        return MemberwiseClone();
    }
}