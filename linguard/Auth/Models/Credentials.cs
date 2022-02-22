namespace Auth.Models; 

public class Credentials : ICredentials {
    public Credentials(string login, string password) {
        Login = login;
        Password = password;
    }
    public string Login { get; }
    public string Password { get; }
}