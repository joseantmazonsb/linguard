namespace Linguard.Core.Configuration; 

public class AuthenticationOptions : IAuthenticationOptions {
    public string DataSource { get; set; }
    
    public object Clone() {
        return MemberwiseClone();
    }
}