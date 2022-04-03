using System.Collections.Concurrent;
using System.Diagnostics;
using System.Net;
using System.Security.Claims;
using Auth.Exceptions;
using Linguard.Web.Auth;
using Linguard.Web.Configuration;
using Microsoft.AspNetCore.Authentication;
using Microsoft.AspNetCore.Authentication.Cookies;
using Microsoft.AspNetCore.Components.Authorization;
using Microsoft.AspNetCore.Identity;
using Microsoft.Extensions.Options;
using Microsoft.JSInterop;
using ICredentials = Auth.Models.ICredentials;

namespace Linguard.Web.Services; 

public class AuthenticationService : IAuthenticationService {
    
    private readonly IHttpContextAccessor _httpContextAccessor;
    private readonly IConfigurationManager _configurationManager;
    private readonly ILogger<IAuthenticationService> _logger;
    private readonly UserManager<IdentityUser> _userManager;
    private readonly SignInManager<IdentityUser> _signInManager;
    private readonly AuthenticationStateProvider _authenticationStateProvider;
    private readonly IHostEnvironmentAuthenticationStateProvider _hostAuthentication;
    private readonly IOptionsMonitor<CookieAuthenticationOptions> _cookieAuthenticationOptionsMonitor;
    private readonly IJSRuntime _jsRuntime;
    private readonly IAuthenticationCookieFormat _cookieFormat = AuthenticationCookieFormat.Default;
    private const string JsNamespace = "authFunctions";
    private static readonly TimeSpan AuthCookieExpireTimeSpan = TimeSpan.FromHours(2);
    private IWebConfiguration WebConfiguration => _configurationManager.Configuration.GetModule<IWebConfiguration>()!;

    public AuthenticationService(ILogger<AuthenticationService> logger, UserManager<IdentityUser> userManager, 
        SignInManager<IdentityUser> signInManager, AuthenticationStateProvider authenticationStateProvider, 
        IHostEnvironmentAuthenticationStateProvider hostAuthentication, IJSRuntime jsRuntime,
        IOptionsMonitor<CookieAuthenticationOptions> cookieAuthenticationOptionsMonitor,
        IConfigurationManager configurationManager, IHttpContextAccessor httpContextAccessor) {
        _logger = logger;
        _userManager = userManager;
        _signInManager = signInManager;
        _authenticationStateProvider = authenticationStateProvider;
        _hostAuthentication = hostAuthentication;
        _cookieAuthenticationOptionsMonitor = cookieAuthenticationOptionsMonitor;
        _jsRuntime = jsRuntime;
        _configurationManager = configurationManager;
        _httpContextAccessor = httpContextAccessor;
    }
    
    private readonly ConcurrentDictionary<IPAddress, int> _loginAttemptsByIpAddress = new();
    private readonly ConcurrentDictionary<IPAddress, Stopwatch> _loginBansByIpAddress = new();

    public TimeSpan BannedFor {
        get {
            var clientIp = _httpContextAccessor.HttpContext?.Connection.RemoteIpAddress;
            if (clientIp == default || !_loginBansByIpAddress.TryGetValue(clientIp, out var stopwatch)) {
                return TimeSpan.Zero;
            }
            if (stopwatch.Elapsed > WebConfiguration.LoginBanTime) {
                _loginBansByIpAddress.TryRemove(clientIp, out _);
                return TimeSpan.Zero;
            }
            return WebConfiguration.LoginBanTime - stopwatch.Elapsed;
        }
    }

    public async Task<IdentityResult> SignUp(ICredentials credentials) {
        var result = await _userManager.CreateAsync(new IdentityUser(credentials.Login), credentials.Password);
        return result;
    }

    public async Task<AuthenticationState> Login(ICredentials credentials) {
        _logger.LogInformation($"Logging in user '{credentials.Login}'...");
        var user = await _userManager.FindByNameAsync(credentials.Login);
        var valid= await _signInManager.UserManager.CheckPasswordAsync(user, credentials.Password);
        if (!valid) {
            AddLoginAttempt();
            throw new LoginException("Invalid credentials.");
        }
        var principal = await _signInManager.CreateUserPrincipalAsync(user);
        var identity = new ClaimsIdentity(principal.Claims, _cookieFormat.Scheme);
        principal = new ClaimsPrincipal(identity);
        _signInManager.Context.User = principal;
        _hostAuthentication.SetAuthenticationState(Task.FromResult(new AuthenticationState(principal)));
        // now the authState is updated
        var authState = await _authenticationStateProvider.GetAuthenticationStateAsync();
        _logger.LogInformation($"User '{credentials.Login}' was successfully logged in.");
        LoginSuccessful();
        await SetLoginCookie(principal);
        return authState;
    }
    
    private void AddLoginAttempt() {
        var clientIp = _httpContextAccessor.HttpContext?.Connection.RemoteIpAddress;
        if (clientIp == default) {
            return;
        }
        _loginAttemptsByIpAddress.TryGetValue(clientIp, out var attempts);
        var attempt = attempts + 1;
        if (!_loginAttemptsByIpAddress.TryUpdate(clientIp, attempt, attempts)) {
            _loginAttemptsByIpAddress.TryAdd(clientIp, attempt);
        }
        if (attempt < WebConfiguration.LoginAttempts) return;
        _loginBansByIpAddress.TryAdd(clientIp, Stopwatch.StartNew());
        _loginAttemptsByIpAddress.TryRemove(clientIp, out _);
    }
    
    private void LoginSuccessful() {
        var clientIp = _httpContextAccessor.HttpContext?.Connection.RemoteIpAddress;
        if (clientIp == default) {
            return;
        }
        _loginAttemptsByIpAddress.TryRemove(clientIp, out _);
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
            value, AuthCookieExpireTimeSpan.TotalSeconds);
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