using Microsoft.AspNetCore.Authentication.Cookies;

namespace Linguard.Web.Auth; 

public class AuthenticationCookieFormatBase : IAuthenticationCookieFormat {
    public AuthenticationCookieFormatBase(string scheme, string name) {
        Scheme = scheme;
        Name = name;
    }
    public string Scheme { get; }
    public string Name { get; }
}

public static class AuthenticationCookieFormat {
    public static readonly IAuthenticationCookieFormat Default =
        new AuthenticationCookieFormatBase(CookieAuthenticationDefaults.AuthenticationScheme, "Auth");
}