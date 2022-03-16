namespace Auth.Exceptions; 

public class LoginException : Exception {
    public LoginException(string message) : base(message) { }
}