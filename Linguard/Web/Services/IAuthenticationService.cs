using Auth.Models;
using Microsoft.AspNetCore.Components.Authorization;
using Microsoft.AspNetCore.Identity;

namespace Linguard.Web.Services; 

public interface IAuthenticationService {
    Task<IdentityResult> SignUp(ICredentials credentials);
    /// <summary>
    /// Try to login a user given its credentials.
    /// </summary>
    /// <param name="credentials"></param>
    /// <returns>The authentication result.</returns>
    Task<AuthenticationState> Login(ICredentials credentials);
    /// <summary>
    /// Logout the currently signed in user.
    /// </summary>
    /// <returns></returns>
    void Logout();
    TimeSpan BannedFor { get; }
}