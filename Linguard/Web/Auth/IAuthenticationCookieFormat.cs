namespace Linguard.Web.Auth; 

public interface IAuthenticationCookieFormat {
    public string Scheme { get; }
    public string Name { get; }
}