namespace Linguard.Core.Services.Exceptions; 

public class WireguardException : Exception {
    public WireguardException() {}
    public WireguardException(string message) : base(message) {}
    public WireguardException(string message, Exception innerException) : base(message, innerException) {}
}