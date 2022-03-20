namespace Linguard.Core.Configuration; 

public class ConfigurationBase : IConfiguration {
    public ConfigurationBase() {
        Modules = new HashSet<IConfigurationModule>();
    }

    public virtual object Clone() {
        var clone = new ConfigurationBase();
        foreach (var module in Modules) {
            clone.Modules.Add((IConfigurationModule) module.Clone());
        }
        return clone;
    }

    public T? GetModule<T>() where T : IConfigurationModule {
        var type = typeof(T);
        return (T?) Modules.SingleOrDefault(m 
            => m.GetType() == type || m.GetType().GetInterface(type.Name) != default);
    }

    public ISet<IConfigurationModule> Modules { get; set; }

    protected bool Equals(ConfigurationBase other) {
        return Modules.SequenceEqual(other.Modules);
    }

    public override bool Equals(object? obj) {
        if (ReferenceEquals(null, obj)) return false;
        if (ReferenceEquals(this, obj)) return true;
        if (obj.GetType() != GetType()) return false;
        return Equals((ConfigurationBase)obj);
    }

    public override int GetHashCode() {
        return Modules.GetHashCode();
    }
}