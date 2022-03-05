using Linguard.Core.Utils;

namespace Linguard.Core.Configuration; 

public class Configuration : IConfiguration {
    public IWireguardConfiguration? Wireguard { get; set; }
    public ILoggingConfiguration? Logging { get; set; }
    public IWebConfiguration? Web { get; set; }
    public ITrafficConfiguration? Traffic { get; set; }
    
    public object Clone() {
        return Cloning.Clone(this);
    }

    protected bool Equals(Configuration other) {
        return Equals(Wireguard, other.Wireguard) 
               && Equals(Logging, other.Logging) 
               && Equals(Web, other.Web)
               && Equals(Traffic, other.Traffic);
    }

    public override bool Equals(object? obj) {
        if (ReferenceEquals(null, obj)) return false;
        if (ReferenceEquals(this, obj)) return true;
        if (obj.GetType() != this.GetType()) return false;
        return Equals((Configuration)obj);
    }

    public override int GetHashCode() {
        return HashCode.Combine(Wireguard, Logging, Web, Traffic);
    }
}