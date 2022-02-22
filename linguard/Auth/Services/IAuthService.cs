using Auth.Models;

namespace Auth.Services; 

public interface IAuthService {
    IToken Login(ICredentials credentials);
    void Logout();
}