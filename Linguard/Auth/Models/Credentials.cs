namespace Auth.Models; 

public class Credentials : ICredentials {
    public string Login { get; set; }
    public string Password { get; set; }
}