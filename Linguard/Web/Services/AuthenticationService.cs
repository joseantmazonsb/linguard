using System.Security.Claims;
using Auth.Exceptions;
using Auth.Models;
using Linguard.Web.Auth;
using Microsoft.AspNetCore.Authentication;
using Microsoft.AspNetCore.Authentication.Cookies;
using Microsoft.AspNetCore.Components.Authorization;
using Microsoft.AspNetCore.Identity;
using Microsoft.Extensions.Options;
using Microsoft.JSInterop;

namespace Linguard.Web.Services; 

public class AuthenticationService : IAuthenticationService {
    
    private readonly ILogger _logger;
    private readonly UserManager<IdentityUser> _userManager;
    private readonly SignInManager<IdentityUser> _signInManager;
    private readonly AuthenticationStateProvider _authenticationStateProvider;
    private readonly IHostEnvironmentAuthenticationStateProvider _hostAuthentication;
    private readonly IOptionsMonitor<CookieAuthenticationOptions> _cookieAuthenticationOptionsMonitor;
    private readonly IJSRuntime _jsRuntime;
    private readonly IAuthenticationCookieFormat _cookieFormat = AuthenticationCookieFormat.Default;
    private const string JsNamespace = "authFunctions";
    
    public AuthenticationService(ILogger logger, UserManager<IdentityUser> userManager, SignInManager<IdentityUser> signInManager, 
        AuthenticationStateProvider authenticationStateProvider, 
        IHostEnvironmentAuthenticationStateProvider hostAuthentication, 
        IOptionsMonitor<CookieAuthenticationOptions> cookieAuthenticationOptionsMonitor, IJSRuntime jsRuntime) {
        _logger = logger;
        _userManager = userManager;
        _signInManager = signInManager;
        _authenticationStateProvider = authenticationStateProvider;
        _hostAuthentication = hostAuthentication;
        _cookieAuthenticationOptionsMonitor = cookieAuthenticationOptionsMonitor;
        _jsRuntime = jsRuntime;
    }
    
    public async Task<AuthenticationState> Login(ICredentials credentials) {
        _logger.LogInformation($"Logging in user '{credentials.Login}'...");
        var user = await _userManager.FindByNameAsync(credentials.Login);
        var valid= await _signInManager.UserManager.CheckPasswordAsync(user, credentials.Password);
        if (!valid) {
            throw new LoginException("Invalid credentials");
        }
        var principal = await _signInManager.CreateUserPrincipalAsync(user);
        var identity = new ClaimsIdentity(principal.Claims, _cookieFormat.Scheme);
        principal = new ClaimsPrincipal(identity);
        _signInManager.Context.User = principal;
        _hostAuthentication.SetAuthenticationState(Task.FromResult(new AuthenticationState(principal)));
        // now the authState is updated
        var authState = await _authenticationStateProvider.GetAuthenticationStateAsync();
        _logger.LogInformation($"User '{credentials.Login}' was successfully logged in.");
        await SetLoginCookie(principal);
        return authState;
    }

    /// <summary>
    /// Create an encrypted authorization ticket and store it as a cookie.
    /// </summary>
    /// <param name="principal"></param>
    /// <returns></returns>
    private ValueTask SetLoginCookie(ClaimsPrincipal principal) {
        // this is where we create a ticket, encrypt it, and invoke a JS method to save the cookie
        var options = _cookieAuthenticationOptionsMonitor.Get(_cookieFormat.Scheme);
        var ticket = new AuthenticationTicket(principal, default, _cookieFormat.Scheme);
        var value = options.TicketDataFormat.Protect(ticket);
        return _jsRuntime.InvokeVoidAsync($"{JsNamespace}.setCookie", _cookieFormat.Name, 
            value, options.ExpireTimeSpan.TotalSeconds);
    }

    public async void Logout() {
        var username = _signInManager.Context.User.Identity?.Name;
        _logger.LogInformation($"Logging out user '{username}'...");
        var principal = _signInManager.Context.User = new ClaimsPrincipal(new ClaimsIdentity());
        _hostAuthentication.SetAuthenticationState(Task.FromResult(new AuthenticationState(principal)));
        await _jsRuntime.InvokeVoidAsync($"{JsNamespace}.deleteCookie", _cookieFormat.Name);
        _logger.LogInformation($"User '{username}' was successfully logged out.");
    }
}