namespace Auth.Models; 

public interface ICredentials {
    public string Login { get; }
    public string Password { get; }
}