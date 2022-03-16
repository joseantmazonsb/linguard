namespace Auth.Models; 

public interface ICredentials {
    public string Login { get; set; }
    public string Password { get; set; }
}